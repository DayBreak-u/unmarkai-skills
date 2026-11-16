"""Offline documentation checks. Run: python3 -m unittest discover -s tests -v."""
import json
from pathlib import Path
import re
import subprocess
import unittest

import jsonschema
import yaml
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parents[1]
CHINA = json.loads((ROOT / 'tests/fixtures/openapi-china-1.3.0.json').read_text())
OVERSEAS = json.loads((ROOT / 'tests/fixtures/openapi-overseas-1.4.0.json').read_text())


def validator(fixture, name):
    document = {
        '$id': 'https://unmarkai.test/openapi-fixture',
        'components': fixture['components'],
    }
    resource = Resource.from_contents(document, default_specification=DRAFT202012)
    registry = resource @ Registry()
    return jsonschema.Draft202012Validator(
        {'$ref': document['$id'] + '#/components/schemas/' + name},
        registry=registry,
        format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
    )


class DocumentationTests(unittest.TestCase):
    def test_documented_json_requests_against_both_regions(self):
        count = 0
        for path in ROOT.rglob('*.md'):
            for block in re.findall(r'```json\n(.*?)```', path.read_text(), re.S):
                body = json.loads(block)
                if body.get('type') in ('video_upscale', 'remove_text'):
                    name = ('VideoUpscaleCreateRequest' if body['type'] == 'video_upscale'
                            else 'RemoveTextJobCreateRequest')
                    validator(CHINA, name).validate(body)
                    validator(OVERSEAS, name).validate(body)
                    count += 1
        self.assertGreaterEqual(count, 2)

    def test_curl_hd_body_offline_both_regions(self):
        path = ROOT / 'skills/unmarkai-video-upscale/references/curl-fallback.md'
        text = path.read_text()
        expression = re.search(r"'(\{type:\"video_upscale\".*?\})'", text).group(1)
        result = subprocess.run(['jq', '-n', '--arg', 'id', 'upl_fixture',
                                 '--arg', 'target', '4k', expression],
                                check=True, capture_output=True, text=True)
        body = json.loads(result.stdout)
        validator(CHINA, 'VideoUpscaleCreateRequest').validate(body)
        validator(OVERSEAS, 'VideoUpscaleCreateRequest').validate(body)

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

    def test_overseas_hd_is_documented_separately_from_china(self):
        docs = {
            path: (ROOT / path).read_text()
            for path in (
                'README.md',
                'README.zh-CN.md',
                'skills/unmarkai-remove-text/references/api-contract.md',
                'skills/unmarkai-video-upscale/SKILL.md',
                'skills/unmarkai-video-upscale/references/curl-fallback.md',
            )
        }
        joined = '\n'.join(docs.values())
        stale = (
            'Never assume HD is available overseas',
            'Do not infer overseas availability',
            '目前官方文档仅说明中国区 REST 接入',
            '共享 OpenAPI 的海外 server 条目不代表海外已开放此能力',
        )
        for phrase in stale:
            self.assertNotIn(phrase, joined)
        contract = docs['skills/unmarkai-remove-text/references/api-contract.md']
        self.assertIn('https://unmarkai.net/openapi-v1.yaml', contract)
        self.assertIn('https://unmarkai.cn/openapi-v1.yaml', contract)
        self.assertIn('https://api.unmarkai.net/v1', contract)
        self.assertIn('all_area', contract)
        self.assertIn('times 1/2/3', contract)
        self.assertIn('CNY 0.04', contract)
        self.assertIn('Do **not** apply China CNY', contract)
        self.assertIn('does **not** name', contract)
        self.assertIn('`video_upscale`', contract)
        self.assertIn('output_resolution', contract)
        self.assertIn('https://unmarkai.net/openapi-v1.yaml', docs['README.md'])
        self.assertIn('all_area', docs['README.md'])
        self.assertIn('https://api.unmarkai.net/v1', docs['README.zh-CN.md'])
        self.assertIn('api.unmarkai.net/v1', docs['skills/unmarkai-video-upscale/references/curl-fallback.md'])
        self.assertEqual(OVERSEAS['info']['version'], '1.4.0')
        self.assertEqual(CHINA['info']['version'], '1.3.0')
        self.assertEqual(OVERSEAS['source'], 'https://unmarkai.net/openapi-v1.yaml')
        self.assertEqual(CHINA['source'], 'https://unmarkai.cn/openapi-v1.yaml')

    def test_watermark_policy_is_regional(self):
        contract = (ROOT / 'skills/unmarkai-remove-text/references/api-contract.md').read_text()
        zh = (ROOT / 'README.zh-CN.md').read_text()
        self.assertNotIn(
            'preserve aspect ratio, frame rate and audio, with no platform\nwatermark on API output',
            contract,
        )
        self.assertIn('China OpenAPI 1.3.0\nstates there is no platform watermark on API output', contract)
        self.assertIn('trial watermark policy follows the\ninternational API account', contract)
        self.assertIn('do not apply the China no-watermark promise to\noverseas jobs', contract)
        self.assertNotIn('保留比例、帧率和音轨，API 成片不加平台水印。', zh)
        self.assertIn('中国区 OpenAPI 1.3.0 承诺 API 成片不加平台水印', zh)
        self.assertIn('试用/水印策略遵循国际站账户政策', zh)
        self.assertIn('不能把国内承诺套到海外', zh)

    def test_curl_poll_times_out_nonzero_without_cancel(self):
        text = (ROOT / 'skills/unmarkai-video-upscale/references/curl-fallback.md').read_text()
        self.assertIn('Job poll timed out; job still pending. JOB_ID=$JOB_ID', text)
        self.assertIn('The server job was not canceled.', text)
        self.assertIn('query later with GET $API/jobs/$JOB_ID', text)
        # The timeout path must exit 1 after the poll loop, not fall through.
        self.assertRegex(
            text,
            r'if \[\[ "\$\(jq -er \.status <<<"\$\{JOB:-\}"\)" != "succeeded" \]\]; then\n'
            r'  echo "Job poll timed out;.*\n'
            r'  exit 1\n'
            r'fi',
        )
        self.assertNotIn('/cancel', text[text.index('Job poll timed out'):text.index('Job poll timed out') + 400])


if __name__ == '__main__':
    unittest.main()
