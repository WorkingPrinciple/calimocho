/* Bounded local image metadata, never an absolute address or full path. LGPL-2.1-or-later */
static void diagnostic_address(const void *address, char *module, SIZE_T capacity, ULONG_PTR *offset)
{
    MEMORY_BASIC_INFORMATION basic;
    char storage[4096];
    MEMORY_SECTION_NAME *section = (void *)storage;
    SIZE_T size, i, start = 0, length;
    const WCHAR *name;
    strcpy(module, "unknown-redacted");
    *offset = 0;
    if (!address || NtQueryVirtualMemory(NtCurrentProcess(), address, MemoryBasicInformation,
                                        &basic, sizeof(basic), &size) || basic.Type != MEM_IMAGE)
        return;
    if (NtQueryVirtualMemory(NtCurrentProcess(), address, MemoryMappedFilenameInformation,
                             section, sizeof(storage), &size)) return;
    name = section->SectionFileName.Buffer;
    length = section->SectionFileName.Length / sizeof(WCHAR);
    if (!length || (const char *)name < storage
        || (const char *)(name + length) > storage + sizeof(storage)) return;
    for (i = 0; i < length; ++i) if (name[i] == '\\' || name[i] == '/') start = i + 1;
    if (length == start || length - start >= capacity) return;
    for (i = start; i < length; ++i)
        if (!((name[i] >= 'a' && name[i] <= 'z') || (name[i] >= 'A' && name[i] <= 'Z')
              || (name[i] >= '0' && name[i] <= '9') || name[i] == '.' || name[i] == '_' || name[i] == '-'))
            return;
    for (i = start; i < length; ++i) module[i - start] = name[i];
    module[length - start] = 0;
    *offset = (ULONG_PTR)address - (ULONG_PTR)basic.AllocationBase;
}
