/*
 * Theme preference pair. Included by system.c to use its app-theme policy.
 * The target ABI is two COLORREFs, not the three-DWORD variant published elsewhere.
 */
struct color_preference
{
    COLORREF color1;
    COLORREF color2;
};

static DWORD preference_palette( COLORREF *palette )
{
    /* Same default palette as Wine's windows.ui/uisettings.c, in COLORREF order. */
    static const COLORREF defaults[7] =
        {0x00ffd8a6, 0x00edb976, 0x00e39c42, 0x00d77800, 0x009e5a00, 0x00754200, 0x00422600};
    DWORD data[8], size = sizeof(data), status;
    unsigned int i;

    status = RegGetValueW( HKEY_CURRENT_USER,
            L"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Accent", L"AccentPalette",
            RRF_RT_REG_BINARY, NULL, data, &size );
    if (status == ERROR_FILE_NOT_FOUND || status == ERROR_PATH_NOT_FOUND)
    {
        for (i = 0; i < 7; ++i) palette[i] = defaults[i];
        return ERROR_SUCCESS;
    }
    if (status) return status;
    if (size != 7 * sizeof(DWORD) && size != 8 * sizeof(DWORD)) return ERROR_INVALID_DATA;
    for (i = 0; i < 7; ++i) palette[i] = data[i] & 0x00ffffff;
    return ERROR_SUCCESS;
}

HRESULT WINAPI GetUserColorPreference( struct color_preference *preference, BOOL force_reload )
{
    COLORREF palette[7];
    DWORD status;

    TRACE( "preference %p, force_reload %d (uncached).\n", preference, force_reload );
    if (!preference)
    {
        WARN( "color_preference reason=null_output.\n" );
        return E_POINTER;
    }
    /* XAML consumes both DWORDs even when the HRESULT is not checked. */
    preference->color1 = GetSysColor( COLOR_BACKGROUND );
    preference->color2 = GetSysColor( COLOR_HIGHLIGHT );
    if ((status = preference_palette( palette )))
    {
        WARN( "color_preference reason=palette status=%lu.\n", status );
        return HRESULT_FROM_WIN32( status );
    }
    preference->color2 = palette[3];
    return S_OK;
}

static COLORREF preference_error( const char *reason, DWORD status, UINT role )
{
    FIXME( "color_preference reason=%s role=%u status=%lu.\n", reason, role, status );
    SetLastError( status );
    return CLR_INVALID;
}

COLORREF WINAPI GetColorFromPreference( const struct color_preference *preference, UINT role,
                                       BOOL ignore_high_contrast, UINT cache_mode )
{
    COLORREF palette[7], color;
    HIGHCONTRASTW contrast = {sizeof(contrast), 0, NULL};
    DWORD status;
    BOOL background;

    TRACE( "preference %p, role %u, ignore_high_contrast %d, cache_mode %u (uncached).\n",
           preference, role, ignore_high_contrast, cache_mode );
    if (!preference) return preference_error( "null_preference", ERROR_INVALID_PARAMETER, role );
    if (cache_mode > 1) return preference_error( "cache_mode", ERROR_INVALID_PARAMETER, role );
    if (role > 7 && (role < 210 || role > 214))
        return preference_error( "unsupported_role", ERROR_NOT_SUPPORTED, role );
    background = role >= 210 && role <= 212;
    if (!ignore_high_contrast)
    {
        if (!SystemParametersInfoW( SPI_GETHIGHCONTRAST, sizeof(contrast), &contrast, 0 ))
        {
            status = GetLastError();
            return preference_error( "high_contrast_query", status ? status : ERROR_GEN_FAILURE, role );
        }
        if (contrast.dwFlags & HCF_HIGHCONTRASTON)
            return 0xff000000 | GetSysColor( role >= 1 && role <= 7 ? COLOR_HIGHLIGHT :
                                            background ? COLOR_WINDOW : COLOR_WINDOWTEXT );
    }
    if (role >= 1 && role <= 7)
    {
        if (role == 4) return 0xff000000 | (preference->color2 & 0x00ffffff);
        if ((status = preference_palette( palette )))
            return preference_error( "palette", status, role );
        if ((preference->color2 & 0x00ffffff) != palette[3])
            return preference_error( "custom_accent_shades", ERROR_NOT_SUPPORTED, role );
        return 0xff000000 | palette[role - 1];
    }
    switch (role)
    {
    case 0:   color = ShouldAppsUseDarkMode() ? RGB(255,255,255) : GetSysColor( COLOR_WINDOWTEXT ); break;
    case 210: color = ShouldAppsUseDarkMode() ? RGB(0,0,0) : GetSysColor( COLOR_WINDOW ); break;
    case 211: color = RGB(255,255,255); break;
    case 212: color = RGB(0,0,0); break;
    case 213: color = RGB(0,0,0); break;
    case 214: color = RGB(255,255,255); break;
    default:  return preference_error( "unsupported_role", ERROR_NOT_SUPPORTED, role );
    }
    return 0xff000000 | color;
}
