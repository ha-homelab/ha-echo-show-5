"""Exercise subprocess cleanup with fake decoders; no audio device is opened."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / 'src' / 'guarded_announce_core.py'
spec = importlib.util.spec_from_file_location('decode_core', PATH)
core = importlib.util.module_from_spec(spec); spec.loader.exec_module(core)

class DecoderTests(unittest.IsolatedAsyncioTestCase):
    async def execute(self, body, timeout=2):
        with tempfile.TemporaryDirectory() as directory:
            program = Path(directory) / 'decoder'
            program.write_text('#!' + sys.executable + '\nimport sys,time\nsys.stdin.buffer.read()\n' + body)
            program.chmod(0o700)
            return await core.decode_pcm(b'encoded-fixture', str(program), timeout=timeout)

    async def test_success_preserves_pcm(self):
        self.assertEqual(await self.execute("sys.stdout.buffer.write(b'\\0\\0' * 50)\n"), b'\0\0' * 50)

    async def test_nonzero_even_with_output_is_failure(self):
        with self.assertRaisesRegex(core.AnnouncementError, 'decode_failed'):
            await self.execute("sys.stdout.buffer.write(b'\\0\\0');sys.exit(1)\n")

    async def test_empty_and_partial_sample_fail(self):
        for body in ['', "sys.stdout.buffer.write(b'x')\n"]:
            with self.subTest(body=body), self.assertRaisesRegex(core.AnnouncementError, 'empty_or_invalid_audio'):
                await self.execute(body)

    async def test_timeout_kills_decoder(self):
        with self.assertRaisesRegex(core.AnnouncementError, 'decode_timeout'):
            await self.execute('time.sleep(20)\n', timeout=0.1)

    async def test_excess_output_is_bounded(self):
        with self.assertRaisesRegex(core.AnnouncementError, 'audio_too_long'):
            await self.execute("sys.stdout.buffer.write(b'0' * 6000000)\n")

    async def test_input_bounds_checked_without_spawn(self):
        for value in (b'', b'x' * (core.MAX_ENCODED_BYTES + 1)):
            with self.subTest(length=len(value)), self.assertRaisesRegex(core.AnnouncementError, 'invalid_audio_size'):
                await core.decode_pcm(value, '/never-execute-this')

    async def test_decoder_receives_only_pipe_protocol(self):
        output = await self.execute("assert sys.argv[sys.argv.index('-protocol_whitelist') + 1] == 'pipe'\nsys.stdout.buffer.write(b'00')\n")
        self.assertEqual(output, b'00')

if __name__ == '__main__': unittest.main()
