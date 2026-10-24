from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from port_d3dmetal import between, port, port_native_gs, port_thread_teb_key, replace_once
sys.path.pop(0)


class PortTests(unittest.TestCase):
    def native_gs_fixture(self):
        signal = (
            "    _thread_set_tsd_base( (uint64_t)amd64_data->pthread_teb );\n"
            "#elif defined __APPLE__\n"
            "    if (!is_inside_signal_stack( data, (void *)RSP_sig(sigcontext )) &&\n"
            "        !is_inside_syscall( data, RSP_sig(sigcontext )))\n"
            "        _thread_set_tsd_base( (uint64_t)data->teb );\n"
            + ('#elif defined __APPLE__\n'
               '                   "syscall\\n\\t" /* _thread_set_tsd_base */\n'
               '#endif\n') * 5
            + ('                   "movq %gs:0x378,%rcx\\n\\t"\n') * 3
            + '                   "2:\\tmovq %gs:0x330,%r10\\n\\t"\n'
            "#elif defined (__APPLE__)\n"
            "    thread_data->pthread_teb = mac_thread_gsbase();"
        )
        loader = (
            "            teb->ThreadLocalStoragePointer = new;\n"
            "    NtCurrentTeb()->ThreadLocalStoragePointer = pointers;\n"
            "        NtCurrentTeb()->ThreadLocalStoragePointer = NULL;\n"
            "    NtCurrentTeb()->FlsSlots = fls_alloc_data();"
        )
        return signal, loader

    def test_native_gs_mirrors_teb_and_keeps_non_apple_frame_loads(self):
        signal, loader = port_native_gs(*self.native_gs_fixture())
        self.assertNotIn("_thread_set_tsd_base", signal)
        self.assertEqual(signal.count('"movq 0x378(%rcx),%rcx'), 3)
        self.assertEqual(signal.count('#else\n                   "movq %gs:0x378'), 3)
        self.assertIn('teb->Instrumentation[0] = thread_data->pthread_teb;', signal)
        for slot in ("Tib.Self", "ThreadLocalStoragePointer", "Peb"):
            self.assertIn(f'"n" (FIELD_OFFSET(TEB, {slot}))', signal)
        self.assertIn('#ifdef __APPLE__', signal)
        for value in ("new", "pointers", "NULL"):
            self.assertIn(f")->ThreadLocalStoragePointer = {value};", loader)
        self.assertEqual(loader.count(
            "#if defined(__x86_64__) && !defined(__arm64ec__)"), 4)
        self.assertIn("&& !NtCurrentTeb()->WowTebOffset", loader)
        self.assertIn(")->TlsExpansionSlots = NtCurrentTeb()->TlsExpansionSlots;", loader)
        self.assertIn("NtTerminateProcess( GetCurrentProcess(), STATUS_NO_MEMORY )", loader)
        self.assertIn("RtlFindClearBitsAndSet( NtCurrentTeb()->Peb->TlsBitmap", loader)

    def test_native_gs_rejects_missing_switch_frame_or_tls_anchor(self):
        signal, loader = self.native_gs_fixture()
        for changed_signal, changed_loader in (
            (signal.replace("/* _thread_set_tsd_base */", "", 1), loader),
            (signal.replace('"movq %gs:0x378,%rcx\\n\\t"', "", 1), loader),
            (signal, loader.replace(" = NULL;", " = other;")),
        ):
            with self.subTest(source=changed_signal[-80:], loader=changed_loader):
                with self.assertRaises(ValueError):
                    port_native_gs(changed_signal, changed_loader)

    def test_replacements_fail_loud_on_missing_or_ambiguous_source(self):
        self.assertEqual(replace_once("one anchor", "anchor", "change"), "one change")
        for content in ("missing", "anchor anchor"):
            with self.assertRaisesRegex(ValueError, "expected one"):
                replace_once(content, "anchor", "change")

    def test_donor_blocks_require_exact_start_and_end(self):
        self.assertEqual(between("before:start body:end", "start", "end"), "start body:")
        for content in ("start only", "start start end"):
            with self.assertRaises(ValueError):
                between(content, "start", "end")

    def test_thread_teb_key_is_initialized_and_used_for_each_thread(self):
        thread = (
            "WINE_DECLARE_DEBUG_CHANNEL(seh);\n"
            "WINE_DECLARE_DEBUG_CHANNEL(threadname);\n"
            "TEB * WINAPI NtCurrentTeb(void)\n"
            "{\n"
            "    struct thread_data *data = get_thread_data();\n"
            "    return data ? data->teb : NULL;\n"
            "}"
        )
        server = (
            "    if (data->teb)\n"
            "    {\n"
            "        init_teb_data( data );\n"
        )
        virtual = (
            "    init_teb( data, ptr );\n"
            "    VIRTUAL_DEBUG_DUMP_VIEW( view );\n"
        )
        unix_private = "extern pthread_key_t thread_data_key;\n"

        thread, server, virtual, unix_private = port_thread_teb_key(
            thread, server, virtual, unix_private)

        self.assertIn("pthread_key_t teb_key = 0;", thread)
        self.assertIn("return pthread_getspecific( teb_key );", thread)
        self.assertIn("pthread_setspecific( teb_key, data->teb );", server)
        self.assertIn("pthread_key_create( &teb_key, NULL );", virtual)
        self.assertIn("pthread_setspecific( teb_key, data->teb );", virtual)
        self.assertIn("extern pthread_key_t teb_key;", unix_private)

    def test_thread_teb_key_port_fails_loudly_on_missing_anchor(self):
        with self.assertRaisesRegex(ValueError, "expected one"):
            port_thread_teb_key(
                "unmatched", "unmatched", "unmatched", "unmatched")

    def test_failed_port_does_not_partially_write_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            donor = root / "donor"
            driver = donor / "dlls/winemac.drv"
            driver.mkdir(parents=True)
            source.mkdir()
            retained = source / "retain"
            retained.write_text("original")
            for name in ("d3dmetal.c", "d3dmetal_objc.m", "d3dmetal_objc.h"):
                (driver / name).write_text("incompatible donor")
            with self.assertRaisesRegex(ValueError, "expected one"):
                port(source, donor)
            self.assertEqual(retained.read_text(), "original")
            self.assertEqual(list(source.iterdir()), [retained])


if __name__ == "__main__":
    unittest.main()
