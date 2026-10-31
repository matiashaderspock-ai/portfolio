"""Synthetic JSON shaping and offline failure-path checks; no credentials/network."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

import update_x_latest as feed


def post(identity='101', text='Building a small public tool.', date='2026-01-02T12:00:00Z', **extra):
    return {'id': identity, 'text': text, 'created_at': date, **extra}


class ShapeTests(unittest.TestCase):
    def test_public_field_whitelist(self):
        source = post(author_id='42', public_metrics={'like_count': 7}, non_public_metrics={'hidden': True})
        result = feed.shape_feed({'data': [source]})
        self.assertFalse(result['sample'])
        item = result['posts'][0]
        self.assertEqual(set(item), {'text', 'type', 'created_date', 'link', 'thumbnail'})
        self.assertEqual(item['created_date'], '2026-01-02')
        self.assertEqual(item['link'], 'https://x.com/pandasczos/status/101')
        self.assertEqual(item['type'], 'post')
        self.assertNotIn('metrics', json.dumps(result))

    def test_posts_quotes_reposts_and_long_text(self):
        quote = post('103', 'A useful idea.', referenced_tweets=[{'type': 'quoted', 'id': '201'}])
        repost = post('104', 'RT truncated', referenced_tweets=[{'type': 'retweeted', 'id': '202'}])
        result = feed.shape_feed({'data': [post(), quote, repost], 'includes': {'tweets': [
            post('201', 'Public source idea.'),
            post('202', 'Short', note_tweet={'text': 'Full public original text.'})]}})
        by_type = {item['type']: item for item in result['posts']}
        self.assertEqual(by_type['repost']['text'], 'Full public original text.')
        self.assertEqual(by_type['repost']['link'], 'https://x.com/i/status/202')
        self.assertEqual(by_type['quote']['text'], 'A useful idea.\n\n↳ Public source idea.')
        self.assertEqual(by_type['quote']['link'], 'https://x.com/pandasczos/status/103')

    def test_latest_five_ordering_and_deduplication(self):
        data = [post(str(i), date=f'2026-01-{i:02}T12:00:00Z') for i in range(1, 9)]
        data.append(deepcopy(data[-1]))
        result = feed.shape_feed({'data': data})['posts']
        self.assertEqual(len(result), 5)
        self.assertEqual([p['created_date'] for p in result], [f'2026-01-{i:02}' for i in range(8, 3, -1)])

    def test_replies_sensitive_withheld_and_invalid_posts_are_excluded(self):
        data = [post('102', referenced_tweets=[{'type': 'replied_to', 'id': '201'}]),
                post('103', possibly_sensitive=True), post('104', withheld={'copyright': True}),
                post('bad-id'), post('105', date='bad date'), post('106', text=''),
                post('107', date='2026-01-01T12:00:00'), post()]
        self.assertEqual(len(feed.shape_feed({'data': data})['posts']), 1)

    def test_financial_and_credential_content_is_excluded(self):
        for text in ['Account balance: private', 'Saldo reservado', 'P&L withheld',
                     'Bearer [redacted]', 'api_key [redacted]', 'link?token=redacted',
                     ''.join(str(i % 10) for i in range(14))]:
            with self.subTest(text=text):
                self.assertEqual(feed.shape_feed({'data': [post(text=text)]})['posts'], [])
        quote = post(referenced_tweets=[{'type': 'quoted', 'id': '201'}])
        self.assertEqual(feed.shape_feed({'data': [quote], 'includes': {'tweets': [post('201', 'Private balance')]}})['posts'], [])

    def test_quoted_currency_amount_is_kept(self):
        quote = post('2115721217307017717', 'A useful research update.',
                     referenced_tweets=[{'type': 'quoted', 'id': '201'}])
        quoted_text = '$52M from @ARPA_H'
        result = feed.shape_feed({'data': [quote], 'includes': {'tweets': [post('201', quoted_text)]}})['posts']
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['type'], 'quote')
        self.assertEqual(result[0]['text'], quote['text'] + '\n\n↳ ' + quoted_text)
        self.assertEqual(result[0]['link'], 'https://x.com/pandasczos/status/2115721217307017717')

    def test_own_currency_amount_is_excluded_from_posts_and_quotes(self):
        for amount in ['$500', '€500', '£500', '¥500', 'USD 500', 'BOB 500', 'Bs. 500']:
            for refs in [[], [{'type': 'quoted', 'id': '201'}]]:
                for long_text in [False, True]:
                    with self.subTest(amount=amount, refs=refs, long_text=long_text):
                        source = post(text='A purchase of ' + amount, referenced_tweets=refs)
                        if long_text:
                            source['note_tweet'] = {'text': source['text']}
                            source['text'] = 'Truncated preview.'
                        result = feed.shape_feed({'data': [source], 'includes': {'tweets': [post('201')]}})
                        self.assertEqual(result['posts'], [])

    def test_reposted_currency_amount_is_kept(self):
        for text in ['$52M from @ARPA_H', '€500', '£500', '¥500', 'USD 500', 'BOB 500', 'Bs. 500']:
            for expanded in [False, True]:
                with self.subTest(text=text, expanded=expanded):
                    repost = post(text='RT ' + text, referenced_tweets=[{'type': 'retweeted', 'id': '201'}])
                    payload = {'data': [repost]}
                    if expanded:
                        payload['includes'] = {'tweets': [post('201', 'Short', note_tweet={'text': text})]}
                    result = feed.shape_feed(payload)['posts']
                    self.assertEqual(len(result), 1)
                    self.assertEqual(result[0]['type'], 'repost')
                    self.assertEqual(result[0]['text'], text if expanded else repost['text'])

    def test_other_sensitive_patterns_still_exclude_quotes_and_reposts(self):
        for text in ['Contact person@example.com', 'api key [redacted]', 'Account balance', 'profit',
                     'ghp_example', 'github_pat_example', 'sk-example', '+1 (202) 555-0123',
                     'https://example.com/?key=redacted', 'https://example.com/?token=redacted',
                     'https://example.com/?auth=redacted', 'https://example.com/?signature=redacted',
                     'https://example.com/?secret=redacted']:
            for kind in ['quoted', 'retweeted']:
                with self.subTest(text=text, kind=kind):
                    source = post(referenced_tweets=[{'type': kind, 'id': '201'}])
                    result = feed.shape_feed({'data': [source], 'includes': {'tweets': [
                        post('201', 'Short', note_tweet={'text': text})]}})
                    self.assertEqual(result['posts'], [])

    def test_only_public_x_thumbnail_urls(self):
        source = post(attachments={'media_keys': ['photo']})
        for value, expected in [('https://pbs.twimg.com/media/example.jpg', True),
                                ('https://pbs.twimg.com/ext_tw_video_thumb/example.jpg', True),
                                ('javascript:alert(1)', False), ('https://pbs.twimg.com.evil.test/media/a', False),
                                ('https://private.example/media/a', False), ('http://pbs.twimg.com/media/a', False)]:
            result = feed.shape_feed({'data': [source], 'includes': {'media': [{'media_key': 'photo', 'url': value}]}})
            self.assertEqual(result['posts'][0]['thumbnail'], value if expected else None)
        unsafe_alt = {'media_key': 'photo', 'url': 'https://pbs.twimg.com/media/example.jpg', 'alt_text': 'Account balance'}
        self.assertIsNone(feed.shape_feed({'data': [source], 'includes': {'media': [unsafe_alt]}})['posts'][0]['thumbnail'])

    def test_missing_expansion_does_not_invent_text(self):
        result = feed.shape_feed({'data': [post(text='Public quote comment.', referenced_tweets=[{'type': 'quoted', 'id': '201'}])]})
        self.assertEqual(result['posts'][0]['text'], 'Public quote comment.')

    def test_empty_feed_and_samples(self):
        self.assertEqual(feed.shape_feed({}), {'sample': False, 'posts': []})
        samples = feed.sample_feed()
        self.assertTrue(samples['sample'])
        self.assertEqual(len(samples['posts']), 5)
        self.assertTrue(all(p['created_date'] is None and p['text'].startswith('Sample') for p in samples['posts']))

    def test_missing_token_writes_samples_without_network(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {'X_BEARER_TOKEN': ''}), patch.object(feed, 'api_get') as api:
            output = Path(directory) / 'feed.json'
            self.assertEqual(feed.main(['--output', str(output)]), 0)
            self.assertTrue(json.loads(output.read_text())['sample'])
            api.assert_not_called()

    def test_explicit_sample_is_always_offline(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {'X_BEARER_TOKEN': '[redacted]'}), patch.object(feed, 'api_get') as api:
            self.assertEqual(feed.main(['--sample', '--output', str(Path(directory) / 'feed.json')]), 0)
            api.assert_not_called()

    def test_failed_api_preserves_existing_feed(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {'X_BEARER_TOKEN': '[redacted]'}), patch.object(feed, 'fetch_feed', side_effect=URLError('unavailable')):
            output = Path(directory) / 'feed.json'
            output.write_text('unchanged')
            self.assertEqual(feed.main(['--output', str(output)]), 1)
            self.assertEqual(output.read_text(), 'unchanged')

    def test_fixture_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture, output = Path(directory) / 'input.json', Path(directory) / 'output.json'
            fixture.write_text(json.dumps({'data': [post()]}))
            self.assertEqual(feed.main(['--fixture', str(fixture), '--output', str(output)]), 0)
            self.assertFalse(json.loads(output.read_text())['sample'])

    def test_protected_profile_is_never_fetched(self):
        with patch.object(feed, 'api_get', return_value={'data': {'id': '42', 'protected': True}}) as api:
            with self.assertRaises(ValueError):
                feed.fetch_feed('[redacted]')
            self.assertEqual(api.call_count, 1)

    def test_api_request_includes_reposts_and_only_public_fields(self):
        replies = [{'data': {'id': '42', 'protected': False}}, {'data': [post()]}]
        with patch.object(feed, 'api_get', side_effect=replies) as api:
            self.assertEqual(len(feed.fetch_feed('[redacted]')['posts']), 1)
            query = api.call_args_list[1].args[2]
            self.assertEqual(query['exclude'], 'replies')
            self.assertNotIn('non_public_metrics', query['tweet.fields'])
            self.assertEqual(api.call_args_list[0].args[0], 'users/by/username/pandasczos')


if __name__ == '__main__':
    unittest.main()
