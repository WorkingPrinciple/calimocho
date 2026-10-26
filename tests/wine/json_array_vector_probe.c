/* Exercises Windows.Data.Json.JsonArray through IVector<IJsonValue>, IVectorView<IJsonValue> and
 * IIterable<IJsonValue>, the way GDK runtimes read endpoint documents. Exit code = failures. */
#define INITGUID
#define COBJMACROS
#include <windows.h>
#include <stdio.h>
#include <roapi.h>
#include <winstring.h>
#include <windows.data.json.h>

typedef __x_ABI_CWindows_CData_CJson_CIJsonValue JV;
typedef __x_ABI_CWindows_CData_CJson_CIJsonArray JA;
typedef __x_ABI_CWindows_CData_CJson_CIJsonObject JO;
typedef __x_ABI_CWindows_CData_CJson_CIJsonValueStatics JVS;
typedef __FIVector_1_Windows__CData__CJson__CIJsonValue VEC;
typedef __FIVectorView_1_Windows__CData__CJson__CIJsonValue VIEW;
typedef __FIIterable_1_Windows__CData__CJson__CIJsonValue ITB;
typedef __FIIterator_1_Windows__CData__CJson__CIJsonValue ITR;

static int failures;
#define CHECK(cond, ...) do { if (cond) printf("PASS "); else { printf("FAIL "); failures++; } printf(__VA_ARGS__); printf("\n"); } while (0)

static HSTRING hs(const WCHAR *s) { HSTRING h = NULL; WindowsCreateString(s, wcslen(s), &h); return h; }

int main(void)
{
    static const WCHAR doc[] = L"{\"EndPoints\":[{\"Host\":\"a\"},{\"Host\":\"b\"},3]}";
    JVS *statics = NULL; JV *root = NULL, *e0 = NULL, *e1 = NULL, *e2 = NULL, *tmp = NULL;
    JO *object = NULL; JA *array = NULL; VEC *vec = NULL; VIEW *view = NULL; ITB *itb = NULL; ITR *itr = NULL;
    UINT32 size = 0, index = 0, count = 0; BOOLEAN found = 0, has = 0; JV *many[8]; HRESULT hr;

    RoInitialize(RO_INIT_MULTITHREADED);
    hr = RoGetActivationFactory(hs(L"Windows.Data.Json.JsonValue"), &IID___x_ABI_CWindows_CData_CJson_CIJsonValueStatics, (void **)&statics);
    CHECK(hr == S_OK, "JsonValue statics hr=0x%08lx", hr);
    if (FAILED(hr)) return 100;
    hr = __x_ABI_CWindows_CData_CJson_CIJsonValueStatics_Parse(statics, hs(doc), &root);
    CHECK(hr == S_OK, "Parse hr=0x%08lx", hr);
    hr = __x_ABI_CWindows_CData_CJson_CIJsonValue_GetObject(root, &object);
    CHECK(hr == S_OK, "GetObject hr=0x%08lx", hr);
    hr = __x_ABI_CWindows_CData_CJson_CIJsonObject_GetNamedArray(object, hs(L"EndPoints"), &array);
    CHECK(hr == S_OK, "GetNamedArray hr=0x%08lx", hr);

    hr = __x_ABI_CWindows_CData_CJson_CIJsonArray_QueryInterface(array, &IID___FIVector_1_Windows__CData__CJson__CIJsonValue, (void **)&vec);
    CHECK(hr == S_OK, "QI IVector<IJsonValue> hr=0x%08lx", hr);
    if (FAILED(hr)) { printf("failures=%d\n", failures); return failures; }
    hr = __FIVector_1_Windows__CData__CJson__CIJsonValue_get_Size(vec, &size);
    CHECK(hr == S_OK && size == 3, "get_Size hr=0x%08lx size=%u", hr, size);
    hr = __FIVector_1_Windows__CData__CJson__CIJsonValue_GetAt(vec, 0, &e0);
    CHECK(hr == S_OK && e0, "GetAt(0) hr=0x%08lx", hr);
    __FIVector_1_Windows__CData__CJson__CIJsonValue_GetAt(vec, 1, &e1);
    __FIVector_1_Windows__CData__CJson__CIJsonValue_GetAt(vec, 2, &e2);
    hr = __FIVector_1_Windows__CData__CJson__CIJsonValue_GetAt(vec, 3, &tmp);
    CHECK(hr == E_BOUNDS, "GetAt(3) out of range hr=0x%08lx", hr);
    { JO *o = NULL; HSTRING host = NULL; UINT32 len = 0;
      hr = __x_ABI_CWindows_CData_CJson_CIJsonValue_GetObject(e1, &o);
      if (SUCCEEDED(hr)) hr = __x_ABI_CWindows_CData_CJson_CIJsonObject_GetNamedString(o, hs(L"Host"), &host);
      CHECK(hr == S_OK && !wcscmp(WindowsGetStringRawBuffer(host, &len), L"b"), "element 1 Host == \"b\" hr=0x%08lx", hr); }
    hr = __FIVector_1_Windows__CData__CJson__CIJsonValue_IndexOf(vec, e1, &index, &found);
    CHECK(hr == S_OK && found && index == 1, "IndexOf(e1) found=%d index=%u", found, index);
    hr = __FIVector_1_Windows__CData__CJson__CIJsonValue_GetMany(vec, 1, 8, many, &count);
    CHECK(hr == S_OK && count == 2 && many[0] == e1, "GetMany(1,8) count=%u", count);

    hr = __FIVector_1_Windows__CData__CJson__CIJsonValue_GetView(vec, &view);
    CHECK(hr == S_OK && view, "GetView hr=0x%08lx", hr);
    hr = __FIVectorView_1_Windows__CData__CJson__CIJsonValue_get_Size(view, &size);
    CHECK(hr == S_OK && size == 3, "view get_Size size=%u", size);

    hr = __x_ABI_CWindows_CData_CJson_CIJsonArray_QueryInterface(array, &IID___FIIterable_1_Windows__CData__CJson__CIJsonValue, (void **)&itb);
    CHECK(hr == S_OK, "QI IIterable<IJsonValue> hr=0x%08lx", hr);
    hr = __FIIterable_1_Windows__CData__CJson__CIJsonValue_First(itb, &itr);
    CHECK(hr == S_OK, "First hr=0x%08lx", hr);
    count = 0;
    while (SUCCEEDED(__FIIterator_1_Windows__CData__CJson__CIJsonValue_get_HasCurrent(itr, &has)) && has)
    {
        hr = __FIIterator_1_Windows__CData__CJson__CIJsonValue_get_Current(itr, &tmp);
        if (SUCCEEDED(hr)) { count++; __x_ABI_CWindows_CData_CJson_CIJsonValue_Release(tmp); }
        __FIIterator_1_Windows__CData__CJson__CIJsonValue_MoveNext(itr, &has);
    }
    CHECK(count == 3, "iterated %u elements", count);

    __FIVector_1_Windows__CData__CJson__CIJsonValue_Append(vec, e0);
    __FIVector_1_Windows__CData__CJson__CIJsonValue_InsertAt(vec, 0, e2);
    __FIVector_1_Windows__CData__CJson__CIJsonValue_get_Size(vec, &size);
    CHECK(size == 5, "Append+InsertAt size=%u", size);
    __FIVectorView_1_Windows__CData__CJson__CIJsonValue_get_Size(view, &size);
    CHECK(size == 5, "view is live size=%u", size);
    __FIVector_1_Windows__CData__CJson__CIJsonValue_RemoveAt(vec, 0);
    __FIVector_1_Windows__CData__CJson__CIJsonValue_SetAt(vec, 3, e1);
    __FIVector_1_Windows__CData__CJson__CIJsonValue_RemoveAtEnd(vec);
    __FIVector_1_Windows__CData__CJson__CIJsonValue_get_Size(vec, &size);
    CHECK(size == 3, "RemoveAt+SetAt+RemoveAtEnd size=%u", size);
    __FIVector_1_Windows__CData__CJson__CIJsonValue_ReplaceAll(vec, 1, &e2);
    __FIVector_1_Windows__CData__CJson__CIJsonValue_GetAt(vec, 0, &tmp);
    __FIVector_1_Windows__CData__CJson__CIJsonValue_get_Size(vec, &size);
    CHECK(size == 1 && tmp == e2, "ReplaceAll size=%u", size);
    __FIVector_1_Windows__CData__CJson__CIJsonValue_Clear(vec);
    __FIVector_1_Windows__CData__CJson__CIJsonValue_get_Size(vec, &size);
    CHECK(size == 0, "Clear size=%u", size);
    hr = __x_ABI_CWindows_CData_CJson_CIJsonArray_GetObjectAt(array, 0, &object);
    CHECK(hr == E_BOUNDS, "IJsonArray sees the cleared vector hr=0x%08lx", hr);

    __FIIterator_1_Windows__CData__CJson__CIJsonValue_Release(itr);
    __FIIterable_1_Windows__CData__CJson__CIJsonValue_Release(itb);
    __FIVectorView_1_Windows__CData__CJson__CIJsonValue_Release(view);
    __FIVector_1_Windows__CData__CJson__CIJsonValue_Release(vec);
    printf("failures=%d\n", failures);
    return failures;
}
