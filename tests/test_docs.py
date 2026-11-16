"""Offline checks; fixture excerpt retrieved 2026-11-16 from its source URL.
Run: python3 -m unittest discover -s tests -v (PyYAML and jsonschema required).
"""
import copy
import json
from pathlib import Path
import re
import subprocess
import unittest

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / 'tests/fixtures/openapi-excerpt.json').read_text())


def schema(name):
    def resolve(value):
        if isinstance(value, dict):
            if '$ref' in value:
                return resolve(CONTRACT['components']['schemas'][value['$ref'].split('/')[-1]])
            return {k: resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [resolve(v) for v in value]
        return value
    return resolve(CONTRACT['components']['schemas'][name])


class DocumentationTests(unittest.TestCase):
    def test_hd_contract_and_invalid_fields(self):
        body = {'type': 'video_upscale', 'input': {'upload_id': 'upl_example'},
                'upscale': {'target': '4k'}}
        for target in ['1080p', '2k', '4k']:
            body['upscale']['target'] = target
            jsonschema.validate(body, schema('VideoUpscaleCreateRequest'))
        for change in [{'target': '720p'}, {'target': '4k', 'fps': 60}, {}]:
            invalid = copy.deepcopy(body)
            invalid['upscale'] = change
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate(invalid, schema('VideoUpscaleCreateRequest'))

    def test_documented_json_requests(self):
        count = 0
        for path in ROOT.rglob('*.md'):
            for block in re.findall(r'```json\n(.*?)```', path.read_text(), re.S):
                body = json.loads(block)
                if body.get('type') in ('video_upscale', 'remove_text'):
                    name = ('VideoUpscaleCreateRequest' if body['type'] == 'video_upscale'
                            else 'RemoveTextJobCreateRequest')
                    jsonschema.validate(body, schema(name))
                    count += 1
        self.assertGreaterEqual(count, 2)

    def test_curl_hd_body_offline(self):
        path = ROOT / 'skills/unmarkai-video-upscale/references/curl-fallback.md'
        text = path.read_text()
        # Evaluate only the documented jq body builder with fixture variables.
        expression = re.search(r"'(\{type:\"video_upscale\".*?\})'", text).group(1)
        result = subprocess.run(['jq', '-n', '--arg', 'id', 'upl_fixture',
                                 '--arg', 'target', '4k', expression],
                                check=True, capture_output=True, text=True)
        jsonschema.validate(json.loads(result.stdout), schema('VideoUpscaleCreateRequest'))

    def test_upload_limits(self):
        body = {'filename': 'source.mp4', 'content_type': 'video/mp4',
                'file_size_bytes': 2147483648}
        jsonschema.validate(body, schema('UploadCreateRequest'))
        body['file_size_bytes'] += 1
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(body, schema('UploadCreateRequest'))

    def test_local_links_and_languages(self):
        for path in ROOT.rglob('*.md'):
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
                if '://' in target or target.startswith('#'):
                    continue
                self.assertTrue((path.parent / target.split('#')[0]).exists(),
                                f'{path.relative_to(ROOT)}: {target}')
        self.assertIn('(README.zh-CN.md)', (ROOT / 'README.md').read_text())
        self.assertIn('(README.md)', (ROOT / 'README.zh-CN.md').read_text())

    def test_shell_syntax(self):
        for path in ROOT.rglob('*.md'):
            for block in re.findall(r'```bash\n(.*?)```', path.read_text(), re.S):
                result = subprocess.run(['bash', '-n'], input=block, text=True,
                                        capture_output=True)
                self.assertEqual(result.returncode, 0, f'{path}: {result.stderr}')

    def test_skill_metadata(self):
        for path in (ROOT / 'skills').glob('*/SKILL.md'):
            metadata = yaml.safe_load(path.read_text().split('---')[1])
            self.assertEqual(metadata['name'], path.parent.name)
            self.assertTrue(metadata['description'])


if __name__ == '__main__':
    unittest.main()
