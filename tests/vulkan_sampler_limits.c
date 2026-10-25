#define VK_NO_PROTOTYPES
#include <vulkan/vulkan.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "Usage: vulkan-sampler-limits ABSOLUTE_LIBRARY\n");
        return 2;
    }
    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) {
        fprintf(stderr, "dlopen: %s\n", dlerror());
        return 2;
    }
    PFN_vkGetInstanceProcAddr get = (PFN_vkGetInstanceProcAddr)dlsym(library, "vkGetInstanceProcAddr");
    if (!get) {
        fprintf(stderr, "Missing vkGetInstanceProcAddr\n");
        return 2;
    }
    PFN_vkCreateInstance create = (PFN_vkCreateInstance)get(VK_NULL_HANDLE, "vkCreateInstance");
    VkApplicationInfo app = {.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
                             .pApplicationName = "REQ104 headless property query",
                             .apiVersion = VK_API_VERSION_1_2};
    VkInstanceCreateInfo info = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
                                .pApplicationInfo = &app};
    VkInstance instance = VK_NULL_HANDLE;
    if (!create || create(&info, NULL, &instance) != VK_SUCCESS) {
        fprintf(stderr, "vkCreateInstance failed\n");
        return 1;
    }
    PFN_vkDestroyInstance destroy = (PFN_vkDestroyInstance)get(instance, "vkDestroyInstance");
    PFN_vkEnumeratePhysicalDevices enumerate =
        (PFN_vkEnumeratePhysicalDevices)get(instance, "vkEnumeratePhysicalDevices");
    PFN_vkGetPhysicalDeviceProperties2 properties =
        (PFN_vkGetPhysicalDeviceProperties2)get(instance, "vkGetPhysicalDeviceProperties2");
    uint32_t count = 0;
    VkPhysicalDevice device = VK_NULL_HANDLE;
    int result = 1;
    if (!destroy || !enumerate || !properties) {
        fprintf(stderr, "Missing instance entrypoint\n");
        return 2;
    }
    if (enumerate(instance, &count, NULL) != VK_SUCCESS || count == 0) {
        fprintf(stderr, "No Vulkan physical device\n");
        goto done;
    }
    VkPhysicalDevice *devices = calloc(count, sizeof(*devices));
    if (!devices) {
        fprintf(stderr, "Cannot allocate device list\n");
        goto done;
    }
    VkResult enumerated = enumerate(instance, &count, devices);
    if (enumerated != VK_SUCCESS || count == 0) {
        fprintf(stderr, "Physical device enumeration failed: %d\n", enumerated);
        free(devices);
        goto done;
    }
    device = devices[0];
    free(devices);
    VkPhysicalDeviceVulkan12Properties p12 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_PROPERTIES};
    VkPhysicalDeviceProperties2 p = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2, .pNext = &p12};
    properties(device, &p);
    printf("{\"ordinary_per_stage_samplers\":%u,\"update_after_bind_per_stage_samplers\":%u,"
           "\"sampler_allocation_limit\":%u,\"logical_device_created\":false,"
           "\"gpu_commands_submitted\":false}\n",
           p.properties.limits.maxPerStageDescriptorSamplers,
           p12.maxPerStageDescriptorUpdateAfterBindSamplers,
           p.properties.limits.maxSamplerAllocationCount);
    /* REQ-104: the shader backport must not spoof ordinary sampler capacity. */
    result = p.properties.limits.maxPerStageDescriptorSamplers == 16 ? 0 : 1;
done:
    destroy(instance, NULL);
    dlclose(library);
    return result;
}
