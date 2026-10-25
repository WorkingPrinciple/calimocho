#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

typedef uint32_t DWORD, COLORREF, UINT;
typedef int32_t HRESULT;
typedef int BOOL;
typedef unsigned char BYTE;
typedef wchar_t WCHAR;
typedef struct { UINT cbSize; DWORD dwFlags; WCHAR *lpszDefaultScheme; } HIGHCONTRASTW;
#define WINAPI
#define TRUE 1
#define FALSE 0
#define S_OK 0
#define E_POINTER ((HRESULT)0x80004003)
#define HRESULT_FROM_WIN32(x) ((HRESULT)(0x80070000 | (x)))
#define ERROR_SUCCESS 0
#define ERROR_FILE_NOT_FOUND 2
#define ERROR_PATH_NOT_FOUND 3
#define ERROR_ACCESS_DENIED 5
#define ERROR_INVALID_DATA 13
#define ERROR_GEN_FAILURE 31
#define ERROR_NOT_SUPPORTED 50
#define ERROR_INVALID_PARAMETER 87
#define HKEY_CURRENT_USER 1
#define RRF_RT_REG_BINARY 8
#define CLR_INVALID 0xffffffff
#define COLOR_BACKGROUND 1
#define COLOR_WINDOW 5
#define COLOR_WINDOWTEXT 8
#define COLOR_HIGHLIGHT 13
#define SPI_GETHIGHCONTRAST 0x42
#define HCF_HIGHCONTRASTON 1
#define RGB(r,g,b) ((COLORREF)((r) | (g) << 8 | (b) << 16))
#define TRACE(...) ((void)0)
#define WARN(...) ((void)0)
static unsigned int diagnostics;
#define FIXME(...) (++diagnostics)
static DWORD last_error, reg_status = ERROR_FILE_NOT_FOUND, data_size = 28, queries;
static DWORD data[8];
static BOOL dark, high_contrast, spi_success = TRUE;

static BOOL wide_equal(const WCHAR *a, const WCHAR *b)
{
    while (*a && *a == *b) { ++a; ++b; }
    return *a == *b;
}

static DWORD RegGetValueW(int key, const WCHAR *path, const WCHAR *name, DWORD flags,
                         DWORD *type, void *buffer, DWORD *size)
{
    assert(key == HKEY_CURRENT_USER && flags == RRF_RT_REG_BINARY);
    assert(wide_equal(path, L"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Accent"));
    assert(wide_equal(name, L"AccentPalette"));
    ++queries;
    if (reg_status) return reg_status;
    assert(*size >= data_size);
    memcpy(buffer, data, data_size);
    *size = data_size;
    return 0;
}
static COLORREF GetSysColor(int color)
{
    switch (color)
    {
    case COLOR_BACKGROUND: return RGB(1,2,3);
    case COLOR_HIGHLIGHT: return RGB(4,5,6);
    case COLOR_WINDOW: return RGB(250,251,252);
    case COLOR_WINDOWTEXT: return RGB(11,12,13);
    }
    assert(0);
    return 0;
}
static BOOL ShouldAppsUseDarkMode(void) { return dark; }
static DWORD GetLastError(void) { return last_error; }
static void SetLastError(DWORD value) { last_error = value; }
static BOOL SystemParametersInfoW(UINT action, UINT size, void *out, UINT flags)
{
    HIGHCONTRASTW *contrast = out;
    assert(action == SPI_GETHIGHCONTRAST && size == sizeof(*contrast) && !flags);
    assert(contrast->cbSize == sizeof(*contrast));
    if (!spi_success) return FALSE;
    contrast->dwFlags = high_contrast ? HCF_HIGHCONTRASTON : 0;
    return TRUE;
}
#include "color_preference_under_test.c"

int main(void)
{
    struct { DWORD before; struct color_preference pref; DWORD after; } guard;
    struct color_preference *pref = &guard.pref;
    static const DWORD expected[7] =
        {0xffffd8a6, 0xffedb976, 0xffe39c42, 0xffd77800, 0xff9e5a00, 0xff754200, 0xff422600};
    unsigned int i, before;
    _Static_assert(sizeof(*pref) == 8, "XAML preference ABI is exactly two COLORREFs");
    memset(&guard, 0xcc, sizeof(guard));
    assert(GetUserColorPreference(NULL, FALSE) == E_POINTER);
    assert(GetUserColorPreference(pref, FALSE) == S_OK);
    assert(guard.before == 0xcccccccc && guard.after == 0xcccccccc);
    assert(pref->color1 == GetSysColor(COLOR_BACKGROUND) && pref->color2 == 0x00d77800);
    for (i = 1; i <= 7; ++i)
        assert(GetColorFromPreference(pref, i, FALSE, 1) == expected[i - 1]);
    assert(GetColorFromPreference(pref, 0, FALSE, 0) == (0xff000000 | GetSysColor(COLOR_WINDOWTEXT)));
    assert(GetColorFromPreference(pref, 210, FALSE, 1) == (0xff000000 | GetSysColor(COLOR_WINDOW)));
    dark = TRUE;
    assert(GetColorFromPreference(pref, 0, FALSE, 1) == 0xffffffff);
    assert(GetColorFromPreference(pref, 210, FALSE, 1) == 0xff000000);
    for (i = 211; i <= 214; ++i)
        assert(GetColorFromPreference(pref, i, TRUE, 0) ==
               (i == 211 || i == 214 ? 0xffffffff : 0xff000000));
    high_contrast = TRUE;
    assert(GetColorFromPreference(pref, 4, FALSE, 0) == (0xff000000 | GetSysColor(COLOR_HIGHLIGHT)));
    assert(GetColorFromPreference(pref, 210, FALSE, 1) == (0xff000000 | GetSysColor(COLOR_WINDOW)));
    assert(GetColorFromPreference(pref, 0, FALSE, 0) == (0xff000000 | GetSysColor(COLOR_WINDOWTEXT)));
    assert(GetColorFromPreference(pref, 4, TRUE, 1) == expected[3]);
    high_contrast = FALSE;
    reg_status = 0;
    data_size = 32;
    for (i = 0; i < 8; ++i) data[i] = RGB(i+10,i+20,i+30) | 0xaa000000;
    before = queries;
    assert(GetUserColorPreference(pref, TRUE) == S_OK && queries == before + 1);
    for (i = 1; i <= 7; ++i)
        assert(GetColorFromPreference(pref, i, TRUE, 0) == (0xff000000 | (data[i - 1] & 0xffffff)));
    data[3] = 0x123456;
    assert(GetUserColorPreference(pref, FALSE) == S_OK && pref->color2 == data[3]);
    assert(GetColorFromPreference(pref, 4, TRUE, 1) == 0xff123456);
    pref->color2 = 0x020304;
    assert(GetColorFromPreference(pref, 4, TRUE, 1) == 0xff020304);
    before = diagnostics;
    assert(GetColorFromPreference(pref, 1, TRUE, 1) == CLR_INVALID && last_error == ERROR_NOT_SUPPORTED);
    assert(diagnostics == before + 1);
    assert(GetColorFromPreference(NULL, 4, TRUE, 1) == CLR_INVALID && last_error == ERROR_INVALID_PARAMETER);
    assert(GetColorFromPreference(pref, 4, TRUE, 2) == CLR_INVALID && last_error == ERROR_INVALID_PARAMETER);
    assert(GetColorFromPreference(pref, 9999, TRUE, 1) == CLR_INVALID && last_error == ERROR_NOT_SUPPORTED);
    data_size = 4;
    assert(GetUserColorPreference(pref, TRUE) == HRESULT_FROM_WIN32(ERROR_INVALID_DATA));
    assert(pref->color1 == GetSysColor(COLOR_BACKGROUND) && pref->color2 == GetSysColor(COLOR_HIGHLIGHT));
    assert(GetColorFromPreference(pref, 2, TRUE, 1) == CLR_INVALID && last_error == ERROR_INVALID_DATA);
    reg_status = ERROR_ACCESS_DENIED;
    memset(pref, 0xcc, 8);
    assert(GetUserColorPreference(pref, FALSE) == HRESULT_FROM_WIN32(ERROR_ACCESS_DENIED));
    assert(pref->color1 == GetSysColor(COLOR_BACKGROUND) && pref->color2 == GetSysColor(COLOR_HIGHLIGHT));
    assert(guard.before == 0xcccccccc && guard.after == 0xcccccccc);
    spi_success = FALSE;
    last_error = ERROR_ACCESS_DENIED;
    assert(GetColorFromPreference(pref, 210, FALSE, 1) == CLR_INVALID && last_error == ERROR_ACCESS_DENIED);
    last_error = 0;
    assert(GetColorFromPreference(pref, 210, FALSE, 0) == CLR_INVALID && last_error == ERROR_GEN_FAILURE);
    assert(GetColorFromPreference(pref, 210, TRUE, 1) == 0xff000000);
    puts("theme preference ABI, roles, high contrast, refresh and explicit failures passed");
    return 0;
}
