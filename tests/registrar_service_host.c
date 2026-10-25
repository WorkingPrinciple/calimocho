#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include <wctype.h>
typedef unsigned DWORD;
typedef unsigned char BYTE;
typedef wchar_t WCHAR;
typedef void *HANDLE;
typedef void *HKEY;
typedef void *PSID;
typedef struct {DWORD LowPart;int HighPart;} LUID;
typedef struct {LUID Luid;DWORD Attributes;} LUID_AND_ATTRIBUTES;
typedef struct {DWORD PrivilegeCount;LUID_AND_ATTRIBUTES Privileges[11];} TOKEN_PRIVILEGES;
typedef struct {PSID Sid;DWORD Attributes;} SID_AND_ATTRIBUTES;
typedef struct {SID_AND_ATTRIBUTES User;} TOKEN_USER;
typedef struct {DWORD GroupCount;SID_AND_ATTRIBUTES Groups[11];} TOKEN_GROUPS;
typedef struct {char SourceName[8];LUID SourceIdentifier;} TOKEN_SOURCE;
typedef struct {unsigned short AclRevision,Sbz1,AclSize,AceCount;} ACL;
typedef struct {ACL *DefaultDacl;} TOKEN_DEFAULT_DACL;
typedef struct {SID_AND_ATTRIBUTES Label;} TOKEN_MANDATORY_LABEL;
typedef struct {DWORD TokenType;LUID AuthenticationId;} TOKEN_STATISTICS;
typedef unsigned TOKEN_INFORMATION_CLASS;
#define TokenUser 1
#define TokenOwner 2
#define TokenPrimaryGroup 3
#define TokenStatistics 4
#define TokenSessionId 5
#define TokenSource 6
#define TokenIntegrityLevel 7
#define TokenRestrictedSids 8
#define TokenGroups 9
#define TokenIsRestricted 10
#define TokenPrivileges 11
#define TokenDefaultDacl 12
#define TokenPrimary 1
#define TOKEN_IMPERSONATE 4
#define TOKEN_QUERY 8
#define TOKEN_DUPLICATE 2
#define TOKEN_ADJUST_PRIVILEGES 32
#define SE_PRIVILEGE_ENABLED 2
#define SecurityImpersonation 2
#define TokenImpersonation 2
#define TRUE 1
#define FALSE 0
#define ERROR_SUCCESS 0
#define ERROR_NO_TOKEN 1008
#define ERROR_ACCESS_DENIED 5
#define ERROR_NOT_SUPPORTED 50
#define ERROR_INVALID_DATA 13
#define SERVICE_WIN32_SHARE_PROCESS 32
#define REG_MULTI_SZ 7
#define KEY_QUERY_VALUE 1
#define HKEY_LOCAL_MACHINE ((void *)1)
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
struct service_entry {
    const WCHAR *name;
    struct {const WCHAR *lpServiceStartName,*lpBinaryPathName;DWORD dwServiceType;} config;
    DWORD sid_type;
};
static DWORD last_error,registry_error,registry_type=REG_MULTI_SZ,registry_size;
static WCHAR registry_members[64];
static int wcsicmp(const WCHAR *a,const WCHAR *b) {
    while(*a&&*b&&towlower(*a)==towlower(*b)) {a++;b++;}
    return towlower(*a)-towlower(*b);
}
static DWORD RegOpenKeyExW(HKEY root,const WCHAR *path,DWORD options,DWORD access,HKEY *key) {*key=(void *)2;return registry_error;}
static DWORD RegQueryValueExW(HKEY key,const WCHAR *name,void *reserved,DWORD *type,BYTE *data,DWORD *size) {
    if(registry_error)return registry_error;
    *type=registry_type;assert(*size>=registry_size);memcpy(data,registry_members,registry_size);
    *size=registry_size;return 0;
}
static void RegCloseKey(HKEY key) {}
static DWORD GetLastError(void) {return last_error;}
static void SetLastError(DWORD error) {last_error=error;}
static unsigned handles,fail_step,step;
static HANDLE installed;
static int failure(void) {if(++step==fail_step){last_error=ERROR_ACCESS_DENIED;return 1;}return 0;}
static void *GetCurrentThread(void) {return (void *)1;}
static void *GetCurrentProcess(void) {return (void *)2;}
static int OpenThreadToken(void *thread,DWORD rights,int self,HANDLE *token) {
    if(failure())return 0;
    if(!installed){last_error=ERROR_NO_TOKEN;return 0;}
    *token=installed;++handles;return 1;
}
static int OpenProcessToken(void *process,DWORD access,HANDLE *token) {
    if(failure())return 0;
    *token=(void *)3;++handles;return 1;
}
static int DuplicateTokenEx(HANDLE token,DWORD access,void *attr,int level,int type,HANDLE *copy) {
    if(failure())return 0;
    *copy=(void *)4;++handles;return 1;
}
static int AdjustTokenPrivileges(HANDLE token,int disable,TOKEN_PRIVILEGES *priv,DWORD size,void *old,void *needed) {
    assert(priv->PrivilegeCount==1&&priv->Privileges[0].Luid.LowPart==7);
    return !failure();
}
static int SetThreadToken(void *thread,HANDLE token) {if(failure())return 0;installed=token;return 1;}
static void CloseHandle(HANDLE token) {assert(handles);--handles;}
static TOKEN_USER expected_user;
static TOKEN_SOURCE expected_source;
static TOKEN_GROUPS expected_groups,expected_restricted;
static TOKEN_PRIVILEGES expected_privileges;
static ACL expected_acl={0,0,sizeof(ACL),0};
static unsigned corrupt_class,failed_class;
static int EqualSid(PSID a,PSID b) {return a&&b&&*(unsigned *)a==*(unsigned *)b;}
static int GetTokenInformation(HANDLE token,unsigned which,void *buffer,DWORD size,DWORD *needed) {
    unsigned bad=0;
    static unsigned bad_sid=999;
    if(which==failed_class){last_error=ERROR_ACCESS_DENIED;return 0;}
    switch(which) {
    case TokenUser:case TokenOwner:case TokenPrimaryGroup:
        *(PSID *)buffer=which==corrupt_class?&bad_sid:expected_user.User.Sid;break;
    case TokenStatistics: {
        TOKEN_STATISTICS value={TokenPrimary,{0x3e5,0}};
        if(which==corrupt_class)value.AuthenticationId.LowPart=0;
        memcpy(buffer,&value,sizeof(value));break;
    }
    case TokenSessionId: *(DWORD *)buffer=which==corrupt_class?1:0;break;
    case TokenSource:
        memcpy(buffer,&expected_source,sizeof(expected_source));
        if(which==corrupt_class)((TOKEN_SOURCE *)buffer)->SourceName[0]='X';break;
    case TokenIntegrityLevel: {
        TOKEN_MANDATORY_LABEL label={{expected_groups.Groups[0].Sid,96}};
        if(which==corrupt_class)label.Label.Attributes=0;
        memcpy(buffer,&label,sizeof(label));break;
    }
    case TokenGroups:case TokenRestrictedSids: {
        TOKEN_GROUPS *expected=which==TokenGroups?&expected_groups:&expected_restricted;
        memcpy(buffer,expected,sizeof(*expected));
        if(which==corrupt_class)((TOKEN_GROUPS *)buffer)->Groups[0].Attributes=0;break;
    }
    case TokenIsRestricted: *(DWORD *)buffer=which==corrupt_class?0:1;break;
    case TokenPrivileges:
        memcpy(buffer,&expected_privileges,sizeof(expected_privileges));
        if(which==corrupt_class)((TOKEN_PRIVILEGES *)buffer)->Privileges[0].Attributes=999;break;
    case TokenDefaultDacl:
        ((TOKEN_DEFAULT_DACL *)buffer)->DefaultDacl=which==corrupt_class?NULL:&expected_acl;break;
    default: assert(bad);
    }
    return 1;
}
#include "registrar_checks_under_test.c"
int main(void) {
    struct service_entry service={L"CoreMessagingRegistrar",
        {L"NT AUTHORITY\\LocalService",L"C:\\windows\\system32\\svchost.exe -k LocalServiceNoNetwork -p",32},3};
    wcscpy(registry_members,service.name);
    registry_size=(wcslen(service.name)+2)*sizeof(WCHAR);
    assert(!registrar_configuration(&service));
    service.sid_type=1;assert(registrar_configuration(&service)==ERROR_NOT_SUPPORTED);service.sid_type=3;
    service.config.lpServiceStartName=L"LocalSystem";
    assert(registrar_configuration(&service)==ERROR_NOT_SUPPORTED);
    service.config.lpServiceStartName=L"NT AUTHORITY\\LocalService";
    registry_members[wcslen(service.name)+1]='X';
    assert(registrar_configuration(&service)==ERROR_NOT_SUPPORTED);
    registry_members[wcslen(service.name)+1]=0;registry_type=1;
    assert(registrar_configuration(&service)==ERROR_NOT_SUPPORTED);
    registry_type=REG_MULTI_SZ;registry_error=ERROR_ACCESS_DENIED;
    assert(registrar_configuration(&service)==ERROR_ACCESS_DENIED);registry_error=0;
    for(unsigned i=1;i<=5;++i) {
        HANDLE previous,scope;installed=(void *)7;handles=0;step=0;fail_step=i;
        assert(registrar_privilege_scope(&previous,&scope)==ERROR_ACCESS_DENIED);
        assert(!handles&&installed==(void *)7&&!previous&&!scope);
    }
    HANDLE previous,scope;installed=(void *)7;handles=0;step=0;fail_step=0;
    assert(!registrar_privilege_scope(&previous,&scope));
    assert(handles==2&&previous==(void *)7&&installed==scope);
    assert(SetThreadToken(NULL,previous));CloseHandle(previous);CloseHandle(scope);assert(!handles);
    unsigned sid=19;
    expected_user.User.Sid=&sid;
    memcpy(expected_source.SourceName,"Advapi  ",8);expected_source.SourceIdentifier.LowPart=123;
    expected_groups.GroupCount=expected_restricted.GroupCount=1;
    expected_groups.Groups[0]=expected_restricted.Groups[0]=(SID_AND_ATTRIBUTES){&sid,96};
    expected_privileges.PrivilegeCount=1;
    expected_privileges.Privileges[0]=(LUID_AND_ATTRIBUTES){{23,0},3};
    for(unsigned i=0;i<=12;++i) {
        corrupt_class=i;
        DWORD result=registrar_token_readback((void *)1,&expected_user,&expected_source,&expected_groups,
                                               &expected_restricted,&expected_privileges,&expected_acl);
        assert(result==(i?ERROR_INVALID_DATA:0));
    }
    corrupt_class=0;
    for(unsigned i=1;i<=12;++i) {
        failed_class=i;
        assert(registrar_token_readback((void *)1,&expected_user,&expected_source,&expected_groups,
                                         &expected_restricted,&expected_privileges,&expected_acl)==ERROR_ACCESS_DENIED);
    }
    return 0;
}
