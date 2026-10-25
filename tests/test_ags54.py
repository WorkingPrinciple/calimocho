"""Source-only tests for the explicitly selected AGS 5.4 non-AMD adapter."""

from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "patches/wine/files/amd_ags_x64"


class AGS54Tests(unittest.TestCase):
    def test_generic_record_has_no_global_ags_override_or_inherited_pass(self):
        root = ROOT / "build/winehq-11.20/metal-port-11d-ags54-02"
        registry = root / "ags54-minidump.registry.local.UNQUALIFIED.json"
        if not registry.is_file():
            self.skipTest("Requires the isolated source-built sibling registry")
        engine = json.loads(registry.read_text())["engines"][0]
        self.assertNotIn("amd_ags", engine["environment"]["WINEDLLOVERRIDES"])
        self.assertEqual(engine["smoke_test"]["status"], "not-run")
        for field in ("graphics_tests", "tls_positive_test", "tls_negative_test",
                      "compiled_source_evidence", "build_evidence"):
            self.assertNotIn(field, engine)
        profile = json.loads((root / "dirt5-ags54.environment.json").read_text())
        self.assertFalse(profile["qualified"])
        self.assertEqual(profile["environment"]["WINEDLLOVERRIDES"], "mscoree,mshtml=;amd_ags_x64=b")
        self.assertEqual(profile["engine"], engine["name"])

    def test_built_module_exports_and_imports(self):
        artifact = ROOT / (
            "build/winehq-11.20/metal-port-11d-ags54-02/install/"
            "lib/wine/x86_64-windows/amd_ags_x64.dll")
        objdump = shutil.which("x86_64-w64-mingw32-objdump")
        if not artifact.is_file() or not objdump:
            self.skipTest("Requires the isolated source-built candidate and installed PE objdump")
        result = subprocess.check_output([objdump, "-p", str(artifact)], text=True, timeout=30)
        self.assertIn("pei-x86-64", result)
        self.assertIn(b"Wine builtin DLL", artifact.read_bytes())
        self.assertIn("DLL Name: d3d12.dll", result)
        self.assertIn("D3D12CreateDevice", result)
        self.assertRegex(result, r"Number in:\s+Export Address Table\s+00000004")
        names = result.split("[Ordinal/Name Pointer] Table -- Ordinal Base 1\n", 1)[1]
        names = names.split("\n\n", 1)[0]
        self.assertEqual([line.split()[-1] for line in names.splitlines()
                          if line.lstrip().startswith("[")], [
            "agsDeInit", "agsDriverExtensionsDX12_CreateDevice",
            "agsDriverExtensionsDX12_DestroyDevice", "agsInit",
        ])

    def test_exact_game_import_surface(self):
        self.assertEqual((SOURCE / "amd_ags_x64.spec").read_text().splitlines(), [
            "@ stdcall agsInit(ptr ptr ptr)",
            "@ stdcall agsDeInit(ptr)",
            "@ stdcall agsDriverExtensionsDX12_CreateDevice(ptr ptr ptr ptr)",
            "@ stdcall agsDriverExtensionsDX12_DestroyDevice(ptr ptr ptr)",
        ])
        self.assertIn("EXTRADLLFLAGS = -Wb,--prefer-native",
                      (SOURCE / "Makefile.in").read_text())

    def test_strings_no_extensions_device_forwarding_and_release(self):
        compiler = shutil.which("cc")
        self.assertIsNotNone(compiler)
        mock_header = r"""
#ifndef MOCK_D3D12_H
#define MOCK_D3D12_H
#include <stdint.h>
typedef void IDXGIAdapter;
typedef void IUnknown;
typedef struct { uint32_t a; uint16_t b, c; unsigned char d[8]; } IID;
typedef IID *REFIID;
typedef int32_t HRESULT;
typedef uint32_t D3D_FEATURE_LEVEL;
typedef unsigned int ULONG;
typedef struct { unsigned int references; } ID3D12Device;
#define WINAPI
#define SUCCEEDED(hr) ((HRESULT)(hr) >= 0)
static HRESULT create_result;
static ID3D12Device device;
static IDXGIAdapter *seen_adapter;
static D3D_FEATURE_LEVEL seen_feature;
static const IID *seen_iid;
static unsigned int releases, creates;
static HRESULT D3D12CreateDevice(IUnknown *adapter, D3D_FEATURE_LEVEL feature,
                                 const IID *iid, void **out)
{
    ++creates;
    seen_adapter = adapter;
    seen_feature = feature;
    seen_iid = iid;
    if (SUCCEEDED(create_result)) { device.references = 2; *out = &device; }
    return create_result;
}
static ULONG ID3D12Device_Release(ID3D12Device *value)
{
    assert(value == &device);
    ++releases;
    return --value->references;
}
#endif
"""
        harness = r"""
#include <assert.h>
#include <stddef.h>
#include <string.h>
#include "main.c"
int main(void)
{
    void *context = NULL;
    struct ags_gpu_info info;
    struct ags_dx12_create_params params = {0};
    struct ags_dx12_returned_params returned;
    unsigned int references = 0xffffffff;
    _Static_assert(sizeof(void *) == 8, "x64 fixture");
    _Static_assert(offsetof(struct ags_gpu_info, driver_version) == 16, "AGS5.4 driver pointer");
    _Static_assert(sizeof(struct ags_gpu_info) == 48, "AGS5.4 info");
    _Static_assert(offsetof(struct ags_dx12_create_params, feature_level) == 24, "AGS5.4 feature");
    _Static_assert(sizeof(struct ags_dx12_returned_params) == 16, "AGS5.4 return record");
    assert(agsInit(NULL, NULL, &info) == AGS_INVALID_ARGS);
    assert(agsInit(&context, NULL, NULL) == AGS_INVALID_ARGS && !context);
    memset(&info, 0xa5, sizeof(info));
    assert(agsInit(&context, NULL, &info) == AGS_SUCCESS && context);
    assert(info.version_major == 5 && info.version_minor == 4 && info.version_patch == 1);
    assert(info.driver_version && !strcmp(info.driver_version, ""));
    assert(info.software_version && !strcmp(info.software_version, ""));
    assert(!info.device_count && !info.devices);
    params.adapter = (void *)(uintptr_t)0x1234;
    params.feature_level = 0xc000;
    create_result = 0;
    memset(&returned, 0xa5, sizeof(returned));
    assert(agsDriverExtensionsDX12_CreateDevice(context, &params, NULL, &returned) == AGS_SUCCESS);
    assert(returned.device == &device && !returned.extensions_supported);
    assert(seen_adapter == params.adapter && seen_feature == params.feature_level && seen_iid == &params.iid);
    assert(agsDriverExtensionsDX12_DestroyDevice(context, returned.device, &references) == AGS_SUCCESS);
    assert(references == 1 && releases == 1);
    create_result = (HRESULT)0x80004005;
    memset(&returned, 0xa5, sizeof(returned));
    assert(agsDriverExtensionsDX12_CreateDevice(context, &params, NULL, &returned) == AGS_FAILURE);
    assert(!returned.device && !returned.extensions_supported && creates == 2);
    assert(agsDriverExtensionsDX12_CreateDevice(NULL, &params, NULL, &returned) == AGS_INVALID_ARGS);
    assert(agsDriverExtensionsDX12_CreateDevice(context, NULL, NULL, &returned) == AGS_INVALID_ARGS);
    assert(agsDriverExtensionsDX12_CreateDevice(context, &params, NULL, NULL) == AGS_INVALID_ARGS);
    assert(agsDriverExtensionsDX12_DestroyDevice(context, NULL, NULL) == AGS_INVALID_ARGS);
    assert(agsDeInit(NULL) == AGS_INVALID_ARGS);
    assert(agsDeInit(context) == AGS_SUCCESS);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "wine").mkdir()
            for header in ("config.h", "windef.h", "winbase.h"):
                (output / header).write_text("")
            (output / "wine/debug.h").write_text(
                "#define WINE_DEFAULT_DEBUG_CHANNEL(name)\n#define WARN(...) ((void)0)\n")
            (output / "d3d12.h").write_text(mock_header)
            (output / "test.c").write_text(harness)
            result = subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                                     "-I" + directory, "-I" + str(SOURCE), str(output / "test.c"),
                                     "-o", str(output / "test")], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(output / "test")], check=True, timeout=10)


if __name__ == "__main__":
    unittest.main()
