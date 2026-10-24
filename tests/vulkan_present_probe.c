/*
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */
#define VK_USE_PLATFORM_WIN32_KHR
#include <windows.h>
#include <vulkan/vulkan.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "probe_window_position.h"

#define WIDTH 320
#define HEIGHT 240
#define FRAMES 120
#define CHECK(label, call) do { \
    status = (call); \
    printf("%s VkResult=%d\n", label, status); \
    if (status != VK_SUCCESS) goto cleanup; \
} while (0)

static LRESULT CALLBACK window_proc(HWND window, UINT message, WPARAM wparam, LPARAM lparam)
{
    return DefWindowProcA(window, message, wparam, lparam);
}

int main(int argc, char **argv)
{
    VkInstance instance = VK_NULL_HANDLE;
    VkPhysicalDevice physical = VK_NULL_HANDLE;
    VkDevice device = VK_NULL_HANDLE;
    VkSurfaceKHR surface = VK_NULL_HANDLE;
    VkSwapchainKHR swapchain = VK_NULL_HANDLE;
    VkQueue queue = VK_NULL_HANDLE;
    VkCommandPool pool = VK_NULL_HANDLE;
    VkCommandBuffer command = VK_NULL_HANDLE;
    VkBuffer buffer = VK_NULL_HANDLE;
    VkDeviceMemory memory = VK_NULL_HANDLE;
    VkSemaphore acquired = VK_NULL_HANDLE, rendered = VK_NULL_HANDLE;
    VkFence fence = VK_NULL_HANDLE;
    VkImage *images = NULL;
    BOOL *initialized = NULL;
    VkPhysicalDevice *devices = NULL;
    VkQueueFamilyProperties *families = NULL;
    VkSurfaceFormatKHR *formats = NULL;
    VkResult status = VK_ERROR_INITIALIZATION_FAILED;
    WNDCLASSA cls = {0};
    HWND window = NULL;
    RECT rect = {0, 0, WIDTH, HEIGHT};
    MSG msg;
    uint32_t count = 0, family = UINT32_MAX, image_count = 0, presented = 0;
    int result = 1;
    int window_x, window_y;
    const char *instance_extensions[] = {VK_KHR_SURFACE_EXTENSION_NAME,
                                         VK_KHR_WIN32_SURFACE_EXTENSION_NAME};
    const char *device_extensions[] = {VK_KHR_SWAPCHAIN_EXTENSION_NAME};
    VkApplicationInfo app = {.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
                            .pApplicationName = "Calimocho Vulkan Probe", .apiVersion = VK_API_VERSION_1_0};
    VkInstanceCreateInfo instance_info = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pApplicationInfo = &app, .enabledExtensionCount = 2, .ppEnabledExtensionNames = instance_extensions};
    VkPhysicalDeviceFeatures features = {0};
    VkSurfaceCapabilitiesKHR caps;
    VkSurfaceFormatKHR format = {0};
    VkPhysicalDeviceProperties properties;
    VkPhysicalDeviceMemoryProperties memory_properties;
    VkMemoryRequirements requirements;
    VkExtent2D extent;
    float priority = 1.0f;
    BOOL require_wide_lines = FALSE;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc == 2 && !strcmp(argv[1], "--require-wide-lines")) require_wide_lines = TRUE;
    else if (argc != 1) { printf("ERROR expected optional --require-wide-lines\n"); return 1; }
    if (!probe_window_position(&window_x, &window_y)) return 1;
    cls.lpfnWndProc = window_proc;
    cls.hInstance = GetModuleHandleA(NULL);
    cls.lpszClassName = "CalimochoVulkanPresentProbe";
    if (!RegisterClassA(&cls) || !AdjustWindowRect(&rect, WS_OVERLAPPEDWINDOW, FALSE))
        goto win32_error;
    window = CreateWindowExA(WS_EX_NOACTIVATE, cls.lpszClassName, "Calimocho Vulkan Present Probe",
        WS_OVERLAPPEDWINDOW, window_x, window_y, rect.right - rect.left, rect.bottom - rect.top,
        NULL, NULL, cls.hInstance, NULL);
    if (!window) goto win32_error;
    if (!SetWindowPos(window, HWND_BOTTOM, 0, 0, 0, 0,
                      SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW))
        goto win32_error;
    printf("window hwnd=%p size=%dx%d no_activate=1\n", window, WIDTH, HEIGHT);
    CHECK("vkCreateInstance", vkCreateInstance(&instance_info, NULL, &instance));
    VkWin32SurfaceCreateInfoKHR surface_info = {.sType = VK_STRUCTURE_TYPE_WIN32_SURFACE_CREATE_INFO_KHR,
        .hinstance = cls.hInstance, .hwnd = window};
    CHECK("vkCreateWin32SurfaceKHR", vkCreateWin32SurfaceKHR(instance, &surface_info, NULL, &surface));
    CHECK("vkEnumeratePhysicalDevices(count)", vkEnumeratePhysicalDevices(instance, &count, NULL));
    if (!count) { printf("ERROR no physical device\n"); goto cleanup; }
    devices = calloc(count, sizeof(*devices));
    if (!devices) goto allocation_error;
    CHECK("vkEnumeratePhysicalDevices", vkEnumeratePhysicalDevices(instance, &count, devices));
    for (uint32_t i = 0; i < count && family == UINT32_MAX; ++i)
    {
        uint32_t family_count = 0;
        vkGetPhysicalDeviceQueueFamilyProperties(devices[i], &family_count, NULL);
        if (!family_count) continue;
        families = calloc(family_count, sizeof(*families));
        if (!families) goto allocation_error;
        vkGetPhysicalDeviceQueueFamilyProperties(devices[i], &family_count, families);
        for (uint32_t j = 0; j < family_count; ++j)
        {
            VkBool32 supported = VK_FALSE;
            CHECK("vkGetPhysicalDeviceSurfaceSupportKHR",
                  vkGetPhysicalDeviceSurfaceSupportKHR(devices[i], j, surface, &supported));
            if (supported && (families[j].queueFlags & VK_QUEUE_GRAPHICS_BIT))
            {
                physical = devices[i];
                family = j;
                break;
            }
        }
        free(families);
        families = NULL;
    }
    if (family == UINT32_MAX) { printf("ERROR no presentation queue\n"); goto cleanup; }
    vkGetPhysicalDeviceProperties(physical, &properties);
    printf("descriptor_limits device=%s vendorID=%u deviceID=%u argument_buffers_env=%s "
           "maxPerStageDescriptorSamplers=%u maxPerStageDescriptorUniformBuffers=%u "
           "maxPerStageDescriptorStorageBuffers=%u maxPerStageDescriptorSampledImages=%u "
           "maxPerStageDescriptorStorageImages=%u maxPerStageDescriptorInputAttachments=%u "
           "maxPerStageResources=%u\n",
           properties.deviceName, properties.vendorID, properties.deviceID,
           getenv("MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS") ?
               getenv("MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS") : "(unset)",
           properties.limits.maxPerStageDescriptorSamplers,
           properties.limits.maxPerStageDescriptorUniformBuffers,
           properties.limits.maxPerStageDescriptorStorageBuffers,
           properties.limits.maxPerStageDescriptorSampledImages,
           properties.limits.maxPerStageDescriptorStorageImages,
           properties.limits.maxPerStageDescriptorInputAttachments,
           properties.limits.maxPerStageResources);
    VkPhysicalDeviceFeatures available_features;
    vkGetPhysicalDeviceFeatures(physical, &available_features);
    if (require_wide_lines && !available_features.wideLines)
    {
        printf("ERROR required wideLines unavailable\n");
        goto cleanup;
    }
    features.wideLines = require_wide_lines ? VK_TRUE : VK_FALSE;
    printf("physical_device=%s api=%u wideLines=%u queue_family=%u\n",
           properties.deviceName, properties.apiVersion, features.wideLines, family);
    printf("wideLines supported=%u required=%u enabled=%u\n",
           available_features.wideLines, require_wide_lines, features.wideLines);
    VkDeviceQueueCreateInfo queue_info = {.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex = family, .queueCount = 1, .pQueuePriorities = &priority};
    VkDeviceCreateInfo device_info = {.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
        .queueCreateInfoCount = 1, .pQueueCreateInfos = &queue_info, .pEnabledFeatures = &features,
        .enabledExtensionCount = 1, .ppEnabledExtensionNames = device_extensions};
    CHECK("vkCreateDevice", vkCreateDevice(physical, &device_info, NULL, &device));
    vkGetDeviceQueue(device, family, 0, &queue);
    CHECK("vkGetPhysicalDeviceSurfaceCapabilitiesKHR",
          vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physical, surface, &caps));
    CHECK("vkGetPhysicalDeviceSurfaceFormatsKHR(count)",
          vkGetPhysicalDeviceSurfaceFormatsKHR(physical, surface, &count, NULL));
    if (!count) { printf("ERROR no surface formats\n"); goto cleanup; }
    formats = calloc(count, sizeof(*formats));
    if (!formats) goto allocation_error;
    CHECK("vkGetPhysicalDeviceSurfaceFormatsKHR",
          vkGetPhysicalDeviceSurfaceFormatsKHR(physical, surface, &count, formats));
    for (uint32_t i = 0; i < count; ++i)
        if (formats[i].format == VK_FORMAT_B8G8R8A8_UNORM ||
            formats[i].format == VK_FORMAT_R8G8B8A8_UNORM)
        {
            format = formats[i];
            break;
        }
    if (!format.format ||
        (caps.supportedUsageFlags & (VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT)) !=
        (VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT))
    {
        printf("ERROR missing UNORM surface or transfer usage\n");
        goto cleanup;
    }
    extent = caps.currentExtent;
    if (extent.width == UINT32_MAX)
    {
        extent.width = WIDTH;
        extent.height = HEIGHT;
        if (extent.width < caps.minImageExtent.width) extent.width = caps.minImageExtent.width;
        if (extent.width > caps.maxImageExtent.width) extent.width = caps.maxImageExtent.width;
        if (extent.height < caps.minImageExtent.height) extent.height = caps.minImageExtent.height;
        if (extent.height > caps.maxImageExtent.height) extent.height = caps.maxImageExtent.height;
    }
    if (!extent.width || !extent.height) { printf("ERROR empty extent\n"); goto cleanup; }
    VkCompositeAlphaFlagBitsKHR alpha = VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR;
    if (!(caps.supportedCompositeAlpha & alpha))
        alpha = (VkCompositeAlphaFlagBitsKHR)(caps.supportedCompositeAlpha & -caps.supportedCompositeAlpha);
    VkSwapchainCreateInfoKHR swap_info = {.sType = VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR,
        .surface = surface, .minImageCount = caps.minImageCount, .imageFormat = format.format,
        .imageColorSpace = format.colorSpace, .imageExtent = extent, .imageArrayLayers = 1,
        .imageUsage = VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT,
        .imageSharingMode = VK_SHARING_MODE_EXCLUSIVE, .preTransform = caps.currentTransform,
        .compositeAlpha = alpha, .presentMode = VK_PRESENT_MODE_FIFO_KHR, .clipped = VK_TRUE};
    CHECK("vkCreateSwapchainKHR", vkCreateSwapchainKHR(device, &swap_info, NULL, &swapchain));
    CHECK("vkGetSwapchainImagesKHR(count)", vkGetSwapchainImagesKHR(device, swapchain, &image_count, NULL));
    if (!image_count) { printf("ERROR no swapchain images\n"); goto cleanup; }
    images = calloc(image_count, sizeof(*images));
    initialized = calloc(image_count, sizeof(*initialized));
    if (!images || !initialized) goto allocation_error;
    CHECK("vkGetSwapchainImagesKHR", vkGetSwapchainImagesKHR(device, swapchain, &image_count, images));
    VkBufferCreateInfo buffer_info = {.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
        .size = (VkDeviceSize)extent.width * extent.height * 4,
        .usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT, .sharingMode = VK_SHARING_MODE_EXCLUSIVE};
    CHECK("vkCreateBuffer", vkCreateBuffer(device, &buffer_info, NULL, &buffer));
    vkGetBufferMemoryRequirements(device, buffer, &requirements);
    vkGetPhysicalDeviceMemoryProperties(physical, &memory_properties);
    uint32_t memory_type = UINT32_MAX;
    for (uint32_t i = 0; i < memory_properties.memoryTypeCount; ++i)
        if ((requirements.memoryTypeBits & (1u << i)) &&
            (memory_properties.memoryTypes[i].propertyFlags &
             (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) ==
            (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))
        {
            memory_type = i;
            break;
        }
    if (memory_type == UINT32_MAX) { printf("ERROR no coherent readback memory\n"); goto cleanup; }
    VkMemoryAllocateInfo memory_info = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .allocationSize = requirements.size, .memoryTypeIndex = memory_type};
    CHECK("vkAllocateMemory", vkAllocateMemory(device, &memory_info, NULL, &memory));
    CHECK("vkBindBufferMemory", vkBindBufferMemory(device, buffer, memory, 0));
    VkCommandPoolCreateInfo pool_info = {.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
        .flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT, .queueFamilyIndex = family};
    CHECK("vkCreateCommandPool", vkCreateCommandPool(device, &pool_info, NULL, &pool));
    VkCommandBufferAllocateInfo command_info = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
        .commandPool = pool, .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1};
    CHECK("vkAllocateCommandBuffers", vkAllocateCommandBuffers(device, &command_info, &command));
    VkSemaphoreCreateInfo semaphore_info = {.sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO};
    VkFenceCreateInfo fence_info = {.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
    CHECK("vkCreateSemaphore(acquired)", vkCreateSemaphore(device, &semaphore_info, NULL, &acquired));
    CHECK("vkCreateSemaphore(rendered)", vkCreateSemaphore(device, &semaphore_info, NULL, &rendered));
    CHECK("vkCreateFence", vkCreateFence(device, &fence_info, NULL, &fence));
    for (uint32_t frame = 0; frame < FRAMES; ++frame)
    {
        uint32_t index;
        while (PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE))
        {
            if (msg.message == WM_QUIT) { printf("ERROR quit\n"); goto cleanup; }
            TranslateMessage(&msg);
            DispatchMessageA(&msg);
        }
        CHECK("vkAcquireNextImageKHR", vkAcquireNextImageKHR(device, swapchain, 5000000000ULL,
              acquired, VK_NULL_HANDLE, &index));
        if (index >= image_count) { printf("ERROR invalid image index\n"); goto cleanup; }
        CHECK("vkResetCommandBuffer", vkResetCommandBuffer(command, 0));
        VkCommandBufferBeginInfo begin = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
            .flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};
        CHECK("vkBeginCommandBuffer", vkBeginCommandBuffer(command, &begin));
        VkImageSubresourceRange range = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
        VkImageMemoryBarrier barrier = {.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
            .srcAccessMask = 0, .dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT,
            .oldLayout = initialized[index] ? VK_IMAGE_LAYOUT_PRESENT_SRC_KHR : VK_IMAGE_LAYOUT_UNDEFINED,
            .newLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
            .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED, .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .image = images[index], .subresourceRange = range};
        vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT,
                             0, 0, NULL, 0, NULL, 1, &barrier);
        VkClearColorValue colour = {.float32 = {0.2f, 0.4f, 0.8f, 1.0f}};
        vkCmdClearColorImage(command, images[index], VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, &colour, 1, &range);
        barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
        barrier.dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
        barrier.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
        barrier.newLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
        vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT,
                             0, 0, NULL, 0, NULL, 1, &barrier);
        if (frame == FRAMES - 1)
        {
            VkBufferImageCopy copy = {.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1},
                                     .imageExtent = {extent.width, extent.height, 1}};
            vkCmdCopyImageToBuffer(command, images[index], VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, buffer, 1, &copy);
            VkBufferMemoryBarrier host = {.sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER,
                .srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT, .dstAccessMask = VK_ACCESS_HOST_READ_BIT,
                .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED, .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                .buffer = buffer, .offset = 0, .size = VK_WHOLE_SIZE};
            vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT,
                                 0, 0, NULL, 1, &host, 0, NULL);
        }
        barrier.srcAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
        barrier.dstAccessMask = 0;
        barrier.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
        barrier.newLayout = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
        vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,
                             0, 0, NULL, 0, NULL, 1, &barrier);
        CHECK("vkEndCommandBuffer", vkEndCommandBuffer(command));
        VkPipelineStageFlags wait_stage = VK_PIPELINE_STAGE_TRANSFER_BIT;
        VkSubmitInfo submit = {.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO,
            .waitSemaphoreCount = 1, .pWaitSemaphores = &acquired, .pWaitDstStageMask = &wait_stage,
            .commandBufferCount = 1, .pCommandBuffers = &command,
            .signalSemaphoreCount = 1, .pSignalSemaphores = &rendered};
        CHECK("vkQueueSubmit", vkQueueSubmit(queue, 1, &submit, fence));
        VkPresentInfoKHR present = {.sType = VK_STRUCTURE_TYPE_PRESENT_INFO_KHR,
            .waitSemaphoreCount = 1, .pWaitSemaphores = &rendered,
            .swapchainCount = 1, .pSwapchains = &swapchain, .pImageIndices = &index};
        CHECK("vkQueuePresentKHR", vkQueuePresentKHR(queue, &present));
        ++presented;
        CHECK("vkWaitForFences", vkWaitForFences(device, 1, &fence, VK_TRUE, 5000000000ULL));
        CHECK("vkQueueWaitIdle", vkQueueWaitIdle(queue));
        CHECK("vkResetFences", vkResetFences(device, 1, &fence));
        initialized[index] = TRUE;
        if (frame == 60)
        {
            printf("capture_ready geometry_only=1\n");
            Sleep(3000);
        }
    }
    void *mapped = NULL;
    CHECK("vkMapMemory", vkMapMemory(device, memory, 0, VK_WHOLE_SIZE, 0, &mapped));
    unsigned char *pixel = (unsigned char *)mapped + ((extent.height / 2) * extent.width + extent.width / 2) * 4;
    unsigned int red = pixel[format.format == VK_FORMAT_B8G8R8A8_UNORM ? 2 : 0];
    unsigned int blue = pixel[format.format == VK_FORMAT_B8G8R8A8_UNORM ? 0 : 2];
    printf("readback RGBA=%u,%u,%u,%u expected=51,102,204,255\n", red, pixel[1], blue, pixel[3]);
    result = presented == FRAMES && red == 51 && pixel[1] == 102 && blue == 204 && pixel[3] == 255 ? 0 : 1;
    vkUnmapMemory(device, memory);
    goto cleanup;

win32_error:
    printf("ERROR window win32=%lu\n", GetLastError());
    goto cleanup;
allocation_error:
    printf("ERROR allocation\n");
cleanup:
    if (device)
    {
        vkDeviceWaitIdle(device);
        if (fence) vkDestroyFence(device, fence, NULL);
        if (acquired) vkDestroySemaphore(device, acquired, NULL);
        if (rendered) vkDestroySemaphore(device, rendered, NULL);
        if (pool) vkDestroyCommandPool(device, pool, NULL);
        if (buffer) vkDestroyBuffer(device, buffer, NULL);
        if (memory) vkFreeMemory(device, memory, NULL);
        if (swapchain) vkDestroySwapchainKHR(device, swapchain, NULL);
        vkDestroyDevice(device, NULL);
    }
    if (surface) vkDestroySurfaceKHR(instance, surface, NULL);
    if (instance) vkDestroyInstance(instance, NULL);
    if (window) DestroyWindow(window);
    free(devices);
    free(families);
    free(formats);
    free(images);
    free(initialized);
    printf("SUMMARY presented=%u expected=120 result=%d\n", presented, result);
    return result;
}
