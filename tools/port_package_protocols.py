"""Apply bounded multi-Application server admission to a NEW cell008 source."""
from pathlib import Path

SERVER_DECLARATION = """static struct wine_package_registration package_registration;
static unsigned int package_registration_image_size;"""

SERVER_TABLE = """#define PACKAGE_REGISTRATION_MAX 32
static struct wine_package_registration package_registrations[PACKAGE_REGISTRATION_MAX];
static unsigned int package_registration_count;

static int registered_package_image( const struct wine_package_identity *package,
                                     const void *image, unsigned int image_size )
{
    unsigned int i, length;
    for (i = 0; i < package_registration_count; ++i)
    {
        const struct wine_package_registration *entry = &package_registrations[i];
        if (memcmp( package, &entry->identity, sizeof(*package) )) continue;
        for (length = 0; entry->image[length]; ++length) {}
        if (image_size == length * sizeof(WCHAR) && !memcmp( image, entry->image, image_size ))
            return 1;
    }
    return 0;
}"""

SERVER_INIT = """void init_package_registration(void)
{
    const char *path = getenv( "CALIMOCHO_PACKAGE_REGISTRATION" );
    struct { unsigned int magic, version, count; } header;
    struct stat st;
    unsigned int i, j;
    ssize_t size;
    int fd;
    char extra;

    if (!path) return;
    fd = open( path, O_RDONLY | O_NOFOLLOW );
    if (fd == -1 || fstat( fd, &st ) || !S_ISREG(st.st_mode)
        || st.st_uid != getuid() || (st.st_mode & 077))
        fatal_error( "Invalid host package registration file\\n" );
    if (st.st_size == sizeof(package_registrations[0]))
        package_registration_count = 1;
    else
    {
        if (read( fd, &header, sizeof(header) ) != sizeof(header)
            || header.magic != 0x52505743 || header.version != 1
            || !header.count || header.count > PACKAGE_REGISTRATION_MAX
            || st.st_size != sizeof(header) + header.count * sizeof(package_registrations[0]))
            fatal_error( "Invalid host package registration table\\n" );
        package_registration_count = header.count;
    }
    size = package_registration_count * sizeof(package_registrations[0]);
    if (read( fd, package_registrations, size ) != size || read( fd, &extra, 1 ) != 0)
        fatal_error( "Cannot read host package registration file\\n" );
    close( fd );
    for (i = 0; i < package_registration_count; ++i)
    {
        struct wine_package_registration *entry = &package_registrations[i];
        if (entry->identity.version != WINE_PACKAGE_VERSION
            || entry->identity.size != sizeof(entry->identity)
            || entry->identity.verified_gamingapp
            || !entry->image[0] || entry->image[1023]
            || !entry->identity.full_name[0] || entry->identity.full_name[255]
            || !entry->identity.family_name[0] || entry->identity.family_name[255]
            || !entry->identity.app_id[0] || entry->identity.app_id[255])
            fatal_error( "Invalid host package registration contents\\n" );
        for (j = 0; j < i; ++j)
            if (!memcmp( entry, &package_registrations[j], sizeof(*entry) ))
                fatal_error( "Duplicate host package registration\\n" );
    }
    unsetenv( "CALIMOCHO_PACKAGE_REGISTRATION" );
}"""

OLD_ADMISSION = """package_registration.identity.size == sizeof(*package)
            && !memcmp( package, &package_registration.identity, sizeof(*package) )
            && info->data->imagepath_len == package_registration_image_size
            && !memcmp( info->data + 1, package_registration.image, info->data->imagepath_len )"""


def port(source):
    source = Path(source).resolve(strict=True)
    path = source / "server/process.c"
    original = path.read_text()
    if original.count(SERVER_DECLARATION) != 1 or original.count(OLD_ADMISSION) != 1:
        raise ValueError("Unexpected server declaration/admission seam")
    start = original.index("void init_package_registration(void)")
    end = original.index("\nstatic const WCHAR process_name[]", start)
    modified = original[:start] + SERVER_INIT + "\n" + original[end:]
    modified = modified.replace(SERVER_DECLARATION, SERVER_TABLE, 1)
    modified = modified.replace(OLD_ADMISSION,
                               "registered_package_image( package, info->data + 1, info->data->imagepath_len )", 1)
    path.write_text(modified)
