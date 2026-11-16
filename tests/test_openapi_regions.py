"""Validate HD requests and responses against official regional schemas."""
import copy
import json
from pathlib import Path
import unittest

import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    'china': json.loads((ROOT / 'tests/fixtures/openapi-china-1.3.0.json').read_text()),
    'overseas': json.loads((ROOT / 'tests/fixtures/openapi-overseas-1.4.0.json').read_text()),
}
FORMAT = jsonschema.Draft202012Validator.FORMAT_CHECKER


def validator(region, name):
    fixture = FIXTURES[region]
    document = {
        '$id': 'https://unmarkai.test/openapi-fixture',
        'components': fixture['components'],
    }
    resource = Resource.from_contents(document, default_specification=DRAFT202012)
    registry = resource @ Registry()
    return jsonschema.Draft202012Validator(
        {'$ref': document['$id'] + '#/components/schemas/' + name},
        registry=registry,
        format_checker=FORMAT,
    )


def valid_create(extra_input=None, **overrides):
    body = {
        'type': 'video_upscale',
        'input': {'upload_id': 'upl_example'},
        'upscale': {'target': '4k'},
    }
    if extra_input:
        body['input'] = {**body['input'], **extra_input}
    body.update(overrides)
    return body


def minimal_job(status='succeeded', currency='USD'):
    succeeded = status == 'succeeded'
    failed = status in {'failed', 'canceled'}
    return {
        'currency': currency,
        'amounts': {'charged': '0.120000'},
        'id': 'job_example',
        'type': 'video_upscale',
        'status': status,
        'input': {'upload_id': 'upl_example'},
        'upscale': {'target': '4k', 'fps': 29.97, 'multiplier': 1},
        'progress': 100 if succeeded else 40,
        'queue_position': None,
        'duration_ms': 30000,
        'provider_duration_ms': 30000 if succeeded else None,
        'billable_seconds': 30 if succeeded else 15,
        'price_version': 'v1',
        'tier': 'tier_100',
        'multiplier_bps': 10000,
        'error': None if not failed else {'code': 'invalid_media', 'message': 'invalid source'},
        'result': (
            {'url': 'https://example.com/enhanced.mp4', 'expires_at': '2026-11-16T08:00:00Z'}
            if succeeded else None
        ),
        'metadata': {},
        'created_at': '2026-11-16T07:00:00Z',
        'updated_at': '2026-11-16T07:00:02Z',
        'queued_at': '2026-11-16T07:00:00Z',
        'processing_at': '2026-11-16T07:00:01Z',
        'terminal_at': '2026-11-16T07:00:02Z' if status in {'succeeded', 'failed', 'canceled'} else None,
    }


class RegionalOpenApiTests(unittest.TestCase):
    def test_fixture_provenance(self):
        self.assertEqual(FIXTURES['china']['source'], 'https://unmarkai.cn/openapi-v1.yaml')
        self.assertEqual(FIXTURES['china']['info']['version'], '1.3.0')
        self.assertEqual(FIXTURES['overseas']['source'], 'https://unmarkai.net/openapi-v1.yaml')
        self.assertEqual(FIXTURES['overseas']['info']['version'], '1.4.0')
        china_input = FIXTURES['china']['components']['schemas']['VideoUpscaleCreateRequest']['properties']['input']
        overseas_input = FIXTURES['overseas']['components']['schemas']['VideoUpscaleCreateRequest']['properties']['input']
        self.assertEqual(china_input, {'$ref': '#/components/schemas/JobInput'})
        self.assertFalse(china_input.get('additionalProperties'))
        self.assertIs(overseas_input['additionalProperties'], False)

    def test_valid_targets_and_upload_limits(self):
        for region in FIXTURES:
            for target in ('1080p', '2k', '4k'):
                body = valid_create()
                body['upscale']['target'] = target
                validator(region, 'VideoUpscaleCreateRequest').validate(body)
            upload = {
                'filename': 'source.mp4',
                'content_type': 'video/mp4',
                'file_size_bytes': 2147483648,
            }
            validator(region, 'UploadCreateRequest').validate(upload)
            too_big = dict(upload, file_size_bytes=2147483649)
            with self.assertRaises(jsonschema.ValidationError):
                validator(region, 'UploadCreateRequest').validate(too_big)

    def test_invalid_create_fields_per_region(self):
        for region in FIXTURES:
            for change in ({'target': '720p'}, {'target': '4k', 'fps': 60}, {}):
                invalid = valid_create()
                invalid['upscale'] = change
                with self.assertRaises(jsonschema.ValidationError):
                    validator(region, 'VideoUpscaleCreateRequest').validate(invalid)

        extra_input = valid_create(extra_input={'unsupported': 'field'})
        with self.assertRaises(jsonschema.ValidationError):
            validator('overseas', 'VideoUpscaleCreateRequest').validate(extra_input)
        # China 1.3.0 $refs JobInput, which does not set additionalProperties: false.
        validator('china', 'VideoUpscaleCreateRequest').validate(extra_input)

    def test_job_response_parsing_per_region(self):
        for region, currency in (('china', 'CNY'), ('overseas', 'USD')):
            job = minimal_job(currency=currency)
            validator(region, 'VideoUpscaleJob').validate(job)
            self.assertEqual(job['type'], 'video_upscale')
            self.assertEqual(job['result']['url'], 'https://example.com/enhanced.mp4')
            self.assertEqual(job['currency'], currency)

            failed = minimal_job(status='failed', currency=currency)
            validator(region, 'VideoUpscaleJob').validate(failed)
            self.assertIsNone(failed['result'])
            self.assertEqual(failed['error']['code'], 'invalid_media')

            invalid = copy.deepcopy(job)
            invalid['result'] = {'expires_at': '2026-11-16T08:00:00Z'}
            with self.assertRaises(jsonschema.ValidationError):
                validator(region, 'VideoUpscaleJob').validate(invalid)


if __name__ == '__main__':
    unittest.main()
