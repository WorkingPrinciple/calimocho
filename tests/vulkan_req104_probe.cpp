// REQ-104 bisect probe for one exact libMoltenVK.dylib. Headless, no Wine, no game.
//   identity: instance only; prints pipeline cache UUID and the sampler limit.
//   tess:     draws one triangle with a vertex+fragment pipeline (control) and
//             with a tessellation pipeline whose vertex stage is the PR 2719
//             fixture, then reads back two pixels.
//   bench:    times encoding of many compute dispatches that use a 128-sampler
//             push descriptor set (pushed once, or before every dispatch) and
//             an ordinary descriptor set of the same shape.
#define VOLK_IMPLEMENTATION
#include <volk.h>
#include <dlfcn.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

static void check(VkResult result, const char* operation) {
    if (result != VK_SUCCESS)
        throw std::runtime_error(std::string(operation) + ": VkResult " + std::to_string(result));
}
#define VK_CHECK(call) check((call), #call)

static std::vector<uint32_t> readSpirv(const std::string& path) {
    std::ifstream input(path, std::ios::binary | std::ios::ate);
    if (!input) throw std::runtime_error("Cannot open " + path);
    auto length = input.tellg();
    if (length <= 0 || length % 4) throw std::runtime_error("Invalid SPIR-V size: " + path);
    std::vector<uint32_t> code(static_cast<size_t>(length) / 4);
    input.seekg(0);
    input.read(reinterpret_cast<char*>(code.data()), length);
    if (!input) throw std::runtime_error("Cannot read " + path);
    return code;
}

struct Probe {
    void* library = nullptr;
    VkInstance instance = VK_NULL_HANDLE;
    VkPhysicalDevice physical = VK_NULL_HANDLE;
    VkPhysicalDeviceProperties properties{};
    VkDevice device = VK_NULL_HANDLE;
    VkQueue queue = VK_NULL_HANDLE;
    uint32_t family = 0;
    VkCommandPool pool = VK_NULL_HANDLE;
    VkFence fence = VK_NULL_HANDLE;
    std::vector<VkShaderModule> modules;
    std::vector<VkPipeline> pipelines;
    std::vector<VkPipelineLayout> pipelineLayouts;
    std::vector<VkDescriptorSetLayout> setLayouts;
    std::vector<VkDescriptorPool> descriptorPools;
    std::vector<VkSampler> samplers;
    std::vector<VkImageView> views;
    std::vector<VkImage> images;
    std::vector<VkBuffer> buffers;
    std::vector<VkDeviceMemory> memories;
    VkRenderPass renderPass = VK_NULL_HANDLE;
    VkFramebuffer framebuffer = VK_NULL_HANDLE;

    ~Probe() {
        // A failed wait is not permission to destroy objects still used by a queue.
        if (device) {
            VkResult idle = vkDeviceWaitIdle(device);
            if (idle != VK_SUCCESS) {
                std::fprintf(stderr, "cleanup vkDeviceWaitIdle: %d\n", idle);
                return;
            }
            if (fence) vkDestroyFence(device, fence, nullptr);
            if (pool) vkDestroyCommandPool(device, pool, nullptr);
            for (auto p : pipelines) vkDestroyPipeline(device, p, nullptr);
            if (framebuffer) vkDestroyFramebuffer(device, framebuffer, nullptr);
            if (renderPass) vkDestroyRenderPass(device, renderPass, nullptr);
            for (auto m : modules) vkDestroyShaderModule(device, m, nullptr);
            for (auto l : pipelineLayouts) vkDestroyPipelineLayout(device, l, nullptr);
            for (auto d : descriptorPools) vkDestroyDescriptorPool(device, d, nullptr);
            for (auto l : setLayouts) vkDestroyDescriptorSetLayout(device, l, nullptr);
            for (auto s : samplers) vkDestroySampler(device, s, nullptr);
            for (auto v : views) vkDestroyImageView(device, v, nullptr);
            for (auto i : images) vkDestroyImage(device, i, nullptr);
            for (auto b : buffers) vkDestroyBuffer(device, b, nullptr);
            for (auto m : memories) vkFreeMemory(device, m, nullptr);
            vkDestroyDevice(device, nullptr);
        }
        if (instance) vkDestroyInstance(instance, nullptr);
        if (library) dlclose(library);
    }

    void createInstance(const char* libraryPath) {
        library = dlopen(libraryPath, RTLD_NOW | RTLD_LOCAL);
        if (!library) throw std::runtime_error(dlerror());
        auto get = reinterpret_cast<PFN_vkGetInstanceProcAddr>(dlsym(library, "vkGetInstanceProcAddr"));
        if (!get) throw std::runtime_error("Missing vkGetInstanceProcAddr");
        volkInitializeCustom(get);
        VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};
        app.pApplicationName = "REQ104 bisect probe";
        app.apiVersion = VK_API_VERSION_1_2;
        VkInstanceCreateInfo ici{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
        ici.pApplicationInfo = &app;
        VK_CHECK(vkCreateInstance(&ici, nullptr, &instance));
        volkLoadInstance(instance);
        uint32_t count = 0;
        VK_CHECK(vkEnumeratePhysicalDevices(instance, &count, nullptr));
        if (!count) throw std::runtime_error("No physical device");
        std::vector<VkPhysicalDevice> devices(count);
        VK_CHECK(vkEnumeratePhysicalDevices(instance, &count, devices.data()));
        physical = devices.front();
        vkGetPhysicalDeviceProperties(physical, &properties);
        char uuid[33] = {};
        for (int i = 0; i < 16; ++i)
            std::snprintf(uuid + 2 * i, 3, "%02x", properties.pipelineCacheUUID[i]);
        std::printf("pipeline_cache_uuid=%s ordinary_limit=%u device=%s\n", uuid,
                    properties.limits.maxPerStageDescriptorSamplers, properties.deviceName);
    }

    void createDevice(const VkPhysicalDeviceFeatures& features, bool push) {
        uint32_t count = 0;
        vkGetPhysicalDeviceQueueFamilyProperties(physical, &count, nullptr);
        std::vector<VkQueueFamilyProperties> families(count);
        vkGetPhysicalDeviceQueueFamilyProperties(physical, &count, families.data());
        family = 0;
        while (family < count && (families[family].queueFlags &
               (VK_QUEUE_GRAPHICS_BIT | VK_QUEUE_COMPUTE_BIT)) != (VK_QUEUE_GRAPHICS_BIT | VK_QUEUE_COMPUTE_BIT))
            ++family;
        if (family == count) throw std::runtime_error("No graphics and compute queue");
        float priority = 1;
        VkDeviceQueueCreateInfo qci{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
        qci.queueFamilyIndex = family; qci.queueCount = 1; qci.pQueuePriorities = &priority;
        const char* extensions[] = {VK_KHR_PUSH_DESCRIPTOR_EXTENSION_NAME};
        VkDeviceCreateInfo dci{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
        dci.queueCreateInfoCount = 1; dci.pQueueCreateInfos = &qci;
        dci.enabledExtensionCount = push ? 1 : 0; dci.ppEnabledExtensionNames = extensions;
        dci.pEnabledFeatures = &features;
        VK_CHECK(vkCreateDevice(physical, &dci, nullptr, &device));
        volkLoadDevice(device);
        vkGetDeviceQueue(device, family, 0, &queue);
        VkCommandPoolCreateInfo cpci{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};
        cpci.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
        cpci.queueFamilyIndex = family;
        VK_CHECK(vkCreateCommandPool(device, &cpci, nullptr, &pool));
        VkFenceCreateInfo fci{VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
        VK_CHECK(vkCreateFence(device, &fci, nullptr, &fence));
    }

    uint32_t memoryType(uint32_t mask, VkMemoryPropertyFlags flags) {
        VkPhysicalDeviceMemoryProperties memory{};
        vkGetPhysicalDeviceMemoryProperties(physical, &memory);
        for (uint32_t i = 0; i < memory.memoryTypeCount; ++i)
            if ((mask & (1u << i)) && (memory.memoryTypes[i].propertyFlags & flags) == flags)
                return i;
        throw std::runtime_error("No required memory type");
    }

    VkDeviceMemory allocate(VkMemoryRequirements req, VkMemoryPropertyFlags flags) {
        VkMemoryAllocateInfo mai{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
        mai.allocationSize = req.size; mai.memoryTypeIndex = memoryType(req.memoryTypeBits, flags);
        VkDeviceMemory memory;
        VK_CHECK(vkAllocateMemory(device, &mai, nullptr, &memory));
        memories.push_back(memory);
        return memory;
    }

    VkBuffer hostBuffer(VkDeviceSize size, VkBufferUsageFlags usage, VkDeviceMemory& memory) {
        VkBufferCreateInfo bci{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
        bci.size = size; bci.usage = usage;
        VkBuffer buffer;
        VK_CHECK(vkCreateBuffer(device, &bci, nullptr, &buffer));
        buffers.push_back(buffer);
        VkMemoryRequirements req{};
        vkGetBufferMemoryRequirements(device, buffer, &req);
        memory = allocate(req, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
        VK_CHECK(vkBindBufferMemory(device, buffer, memory, 0));
        return buffer;
    }

    VkShaderModule module(const std::string& path) {
        auto code = readSpirv(path);
        VkShaderModuleCreateInfo smci{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};
        smci.codeSize = code.size() * 4; smci.pCode = code.data();
        VkShaderModule result;
        VK_CHECK(vkCreateShaderModule(device, &smci, nullptr, &result));
        modules.push_back(result);
        return result;
    }

    VkCommandBuffer beginCommands() {
        VkCommandBufferAllocateInfo cai{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
        cai.commandPool = pool; cai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY; cai.commandBufferCount = 1;
        VkCommandBuffer cmd;
        VK_CHECK(vkAllocateCommandBuffers(device, &cai, &cmd));
        VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
        VK_CHECK(vkBeginCommandBuffer(cmd, &begin));
        return cmd;
    }

    // Returns {submit seconds, submit-to-completion seconds}.
    std::pair<double, double> submitAndWait(VkCommandBuffer cmd) {
        VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};
        submit.commandBufferCount = 1; submit.pCommandBuffers = &cmd;
        auto start = std::chrono::steady_clock::now();
        VK_CHECK(vkQueueSubmit(queue, 1, &submit, fence));
        auto submitted = std::chrono::steady_clock::now();
        VK_CHECK(vkWaitForFences(device, 1, &fence, VK_TRUE, 30000000000ull));
        auto done = std::chrono::steady_clock::now();
        VK_CHECK(vkResetFences(device, 1, &fence));
        return {std::chrono::duration<double>(submitted - start).count(),
                std::chrono::duration<double>(done - start).count()};
    }

    int tess(const std::string& dir) {
        VkPhysicalDeviceFeatures available{};
        vkGetPhysicalDeviceFeatures(physical, &available);
        if (!available.tessellationShader) throw std::runtime_error("Tessellation unavailable");
        VkPhysicalDeviceFeatures features{};
        features.tessellationShader = VK_TRUE;
        createDevice(features, false);
        const uint32_t size = 64;
        VkImageCreateInfo im{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
        im.imageType = VK_IMAGE_TYPE_2D; im.format = VK_FORMAT_R8G8B8A8_UNORM;
        im.extent = {size, size, 1}; im.mipLevels = 1; im.arrayLayers = 1;
        im.samples = VK_SAMPLE_COUNT_1_BIT; im.tiling = VK_IMAGE_TILING_OPTIMAL;
        im.usage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT;
        VkImage image;
        VK_CHECK(vkCreateImage(device, &im, nullptr, &image));
        images.push_back(image);
        VkMemoryRequirements req{};
        vkGetImageMemoryRequirements(device, image, &req);
        VK_CHECK(vkBindImageMemory(device, image, allocate(req, 0), 0));
        VkImageViewCreateInfo vci{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};
        vci.image = image; vci.viewType = VK_IMAGE_VIEW_TYPE_2D; vci.format = im.format;
        vci.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
        VkImageView view;
        VK_CHECK(vkCreateImageView(device, &vci, nullptr, &view));
        views.push_back(view);
        VkAttachmentDescription attachment{};
        attachment.format = im.format; attachment.samples = VK_SAMPLE_COUNT_1_BIT;
        attachment.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR; attachment.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
        attachment.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
        attachment.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
        attachment.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
        attachment.finalLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
        VkAttachmentReference ref{0, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
        VkSubpassDescription subpass{};
        subpass.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
        subpass.colorAttachmentCount = 1; subpass.pColorAttachments = &ref;
        VkSubpassDependency dependency{};
        dependency.srcSubpass = 0; dependency.dstSubpass = VK_SUBPASS_EXTERNAL;
        dependency.srcStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
        dependency.dstStageMask = VK_PIPELINE_STAGE_TRANSFER_BIT;
        dependency.srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
        dependency.dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
        VkRenderPassCreateInfo rpci{VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO};
        rpci.attachmentCount = 1; rpci.pAttachments = &attachment;
        rpci.subpassCount = 1; rpci.pSubpasses = &subpass;
        rpci.dependencyCount = 1; rpci.pDependencies = &dependency;
        VK_CHECK(vkCreateRenderPass(device, &rpci, nullptr, &renderPass));
        VkFramebufferCreateInfo fbci{VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO};
        fbci.renderPass = renderPass; fbci.attachmentCount = 1; fbci.pAttachments = &view;
        fbci.width = fbci.height = size; fbci.layers = 1;
        VK_CHECK(vkCreateFramebuffer(device, &fbci, nullptr, &framebuffer));
        VkDeviceMemory vertexMemory, readbackMemory;
        VkBuffer vertices = hostBuffer(3 * 16, VK_BUFFER_USAGE_VERTEX_BUFFER_BIT, vertexMemory);
        VkBuffer readback = hostBuffer(size * size * 4, VK_BUFFER_USAGE_TRANSFER_DST_BIT, readbackMemory);
        // Top-left triangle in normalized device coordinates.
        const float corners[12] = {-1, -1, 0, 1,  0, -1, 0, 1,  -1, 0, 0, 1};
        void* mapped = nullptr;
        VK_CHECK(vkMapMemory(device, vertexMemory, 0, sizeof(corners), 0, &mapped));
        std::memcpy(mapped, corners, sizeof(corners));
        vkUnmapMemory(device, vertexMemory);
        VkPipelineLayoutCreateInfo plci{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
        VkPipelineLayout layout;
        VK_CHECK(vkCreatePipelineLayout(device, &plci, nullptr, &layout));
        pipelineLayouts.push_back(layout);
        VkShaderModule vert = module(dir + "/spirv_vertex_output.spv");
        VkShaderModule tesc = module(dir + "/spirv_tess_control.spv");
        VkShaderModule tese = module(dir + "/spirv_tess_eval.spv");
        VkShaderModule frag = module(dir + "/spirv_fragment_red.spv");
        int status = 0;
        for (bool tessellated : {false, true}) {
            const char* name = tessellated ? "tess" : "plain";
            std::vector<VkPipelineShaderStageCreateInfo> stages{
                {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, nullptr, 0,
                 VK_SHADER_STAGE_VERTEX_BIT, vert, "main", nullptr}};
            if (tessellated) {
                stages.push_back({VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, nullptr, 0,
                                  VK_SHADER_STAGE_TESSELLATION_CONTROL_BIT, tesc, "main", nullptr});
                stages.push_back({VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, nullptr, 0,
                                  VK_SHADER_STAGE_TESSELLATION_EVALUATION_BIT, tese, "main", nullptr});
            }
            stages.push_back({VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, nullptr, 0,
                              VK_SHADER_STAGE_FRAGMENT_BIT, frag, "main", nullptr});
            VkVertexInputBindingDescription binding{0, 16, VK_VERTEX_INPUT_RATE_VERTEX};
            VkVertexInputAttributeDescription attribute{0, 0, VK_FORMAT_R32G32B32A32_SFLOAT, 0};
            VkPipelineVertexInputStateCreateInfo vi{VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};
            vi.vertexBindingDescriptionCount = 1; vi.pVertexBindingDescriptions = &binding;
            vi.vertexAttributeDescriptionCount = 1; vi.pVertexAttributeDescriptions = &attribute;
            VkPipelineInputAssemblyStateCreateInfo ia{VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO};
            ia.topology = tessellated ? VK_PRIMITIVE_TOPOLOGY_PATCH_LIST : VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
            VkPipelineTessellationStateCreateInfo ts{VK_STRUCTURE_TYPE_PIPELINE_TESSELLATION_STATE_CREATE_INFO};
            ts.patchControlPoints = 3;
            VkViewport viewport{0, 0, float(size), float(size), 0, 1};
            VkRect2D scissor{{0, 0}, {size, size}};
            VkPipelineViewportStateCreateInfo vp{VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO};
            vp.viewportCount = vp.scissorCount = 1; vp.pViewports = &viewport; vp.pScissors = &scissor;
            VkPipelineRasterizationStateCreateInfo rs{VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO};
            rs.polygonMode = VK_POLYGON_MODE_FILL; rs.cullMode = VK_CULL_MODE_NONE; rs.lineWidth = 1;
            VkPipelineMultisampleStateCreateInfo ms{VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO};
            ms.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;
            VkPipelineColorBlendAttachmentState blendAttachment{};
            blendAttachment.colorWriteMask = VK_COLOR_COMPONENT_R_BIT | VK_COLOR_COMPONENT_G_BIT |
                                             VK_COLOR_COMPONENT_B_BIT | VK_COLOR_COMPONENT_A_BIT;
            VkPipelineColorBlendStateCreateInfo blend{VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO};
            blend.attachmentCount = 1; blend.pAttachments = &blendAttachment;
            VkGraphicsPipelineCreateInfo gpci{VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO};
            gpci.stageCount = static_cast<uint32_t>(stages.size()); gpci.pStages = stages.data();
            gpci.pVertexInputState = &vi; gpci.pInputAssemblyState = &ia;
            gpci.pTessellationState = tessellated ? &ts : nullptr;
            gpci.pViewportState = &vp; gpci.pRasterizationState = &rs;
            gpci.pMultisampleState = &ms; gpci.pColorBlendState = &blend;
            gpci.layout = layout; gpci.renderPass = renderPass;
            VkPipeline pipeline = VK_NULL_HANDLE;
            VkResult created = vkCreateGraphicsPipelines(device, VK_NULL_HANDLE, 1, &gpci, nullptr, &pipeline);
            std::printf("%s_pipeline=%d\n", name, created);
            std::fflush(stdout);
            if (created != VK_SUCCESS) {
                if (pipeline) vkDestroyPipeline(device, pipeline, nullptr);
                if (!tessellated) return 1;
                return 3;
            }
            pipelines.push_back(pipeline);
            VkCommandBuffer cmd = beginCommands();
            VkClearValue clear{};
            VkRenderPassBeginInfo ri{VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO};
            ri.renderPass = renderPass; ri.framebuffer = framebuffer;
            ri.renderArea = {{0, 0}, {size, size}}; ri.clearValueCount = 1; ri.pClearValues = &clear;
            vkCmdBeginRenderPass(cmd, &ri, VK_SUBPASS_CONTENTS_INLINE);
            vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline);
            VkDeviceSize offset = 0;
            vkCmdBindVertexBuffers(cmd, 0, 1, &vertices, &offset);
            vkCmdDraw(cmd, 3, 1, 0, 0);
            vkCmdEndRenderPass(cmd);
            VkBufferImageCopy copy{};
            copy.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1};
            copy.imageExtent = {size, size, 1};
            vkCmdCopyImageToBuffer(cmd, image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, readback, 1, &copy);
            VkMemoryBarrier host{VK_STRUCTURE_TYPE_MEMORY_BARRIER};
            host.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT; host.dstAccessMask = VK_ACCESS_HOST_READ_BIT;
            vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT,
                                 0, 1, &host, 0, nullptr, 0, nullptr);
            VK_CHECK(vkEndCommandBuffer(cmd));
            submitAndWait(cmd);
            vkFreeCommandBuffers(device, pool, 1, &cmd);
            VK_CHECK(vkMapMemory(device, readbackMemory, 0, size * size * 4, 0, &mapped));
            const uint32_t* pixels = static_cast<const uint32_t*>(mapped);
            uint32_t inside = pixels[8 * size + 8];
            uint32_t outside = pixels[56 * size + 56];
            vkUnmapMemory(device, readbackMemory);
            // REQ-104: the triangle covers (8,8) and not (56,56) only when every
            // vertex output component reached the next stage unchanged.
            bool pass = inside == 0xff0000ffu && outside == 0x00000000u;
            std::printf("%s_inside=0x%08x %s_outside=0x%08x %s_result=%s\n", name, inside, name, outside,
                        name, pass ? "PASS" : "FAIL");
            if (!pass) status = 1;
        }
        return status;
    }

    int bench(const std::string& shaderPath, uint32_t dispatches, uint32_t repeats) {
        const uint32_t width = 128;
        if (properties.limits.maxPerStageDescriptorSamplers < width) {
            std::fprintf(stderr, "SKIP: advertised sampler limit below %u\n", width);
            return 77;
        }
        createDevice(VkPhysicalDeviceFeatures{}, true);
        if (!vkCmdPushDescriptorSetKHR) throw std::runtime_error("Push descriptor entrypoint unavailable");
        VkDeviceMemory outputMemory;
        VkBuffer output = hostBuffer(8, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT, outputMemory);
        VkImageCreateInfo im{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
        im.imageType = VK_IMAGE_TYPE_2D; im.format = VK_FORMAT_R32_SFLOAT;
        im.extent = {1, 1, 1}; im.mipLevels = 1; im.arrayLayers = 1;
        im.samples = VK_SAMPLE_COUNT_1_BIT; im.tiling = VK_IMAGE_TILING_OPTIMAL;
        im.usage = VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT;
        VkImage image;
        VK_CHECK(vkCreateImage(device, &im, nullptr, &image));
        images.push_back(image);
        VkMemoryRequirements req{};
        vkGetImageMemoryRequirements(device, image, &req);
        VK_CHECK(vkBindImageMemory(device, image, allocate(req, 0), 0));
        VkImageViewCreateInfo vci{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};
        vci.image = image; vci.viewType = VK_IMAGE_VIEW_TYPE_2D; vci.format = im.format;
        vci.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
        VkImageView view;
        VK_CHECK(vkCreateImageView(device, &vci, nullptr, &view));
        views.push_back(view);
        VkSamplerCreateInfo sci{VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO};
        sci.magFilter = sci.minFilter = VK_FILTER_NEAREST;
        sci.addressModeU = sci.addressModeV = sci.addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
        VkSampler sampler;
        VK_CHECK(vkCreateSampler(device, &sci, nullptr, &sampler));
        samplers.push_back(sampler);
        std::array<VkDescriptorSetLayoutBinding, 3> bindings{{
            {0, VK_DESCRIPTOR_TYPE_SAMPLER, width, VK_SHADER_STAGE_COMPUTE_BIT, nullptr},
            {1, VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, 1, VK_SHADER_STAGE_COMPUTE_BIT, nullptr},
            {2, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1, VK_SHADER_STAGE_COMPUTE_BIT, nullptr}}};
        VkShaderModule shader = module(shaderPath);
        std::array<VkPipeline, 2> pipeline{};
        std::array<VkPipelineLayout, 2> layout{};
        for (uint32_t push = 0; push < 2; ++push) {
            VkDescriptorSetLayoutCreateInfo lci{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
            lci.flags = push ? VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR : 0;
            lci.bindingCount = 3; lci.pBindings = bindings.data();
            VkDescriptorSetLayout setLayout;
            VK_CHECK(vkCreateDescriptorSetLayout(device, &lci, nullptr, &setLayout));
            setLayouts.push_back(setLayout);
            VkPushConstantRange range{VK_SHADER_STAGE_COMPUTE_BIT, 0, 4};
            VkPipelineLayoutCreateInfo plci{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
            plci.setLayoutCount = 1; plci.pSetLayouts = &setLayout;
            plci.pushConstantRangeCount = 1; plci.pPushConstantRanges = &range;
            VK_CHECK(vkCreatePipelineLayout(device, &plci, nullptr, &layout[push]));
            pipelineLayouts.push_back(layout[push]);
            VkComputePipelineCreateInfo pci{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};
            pci.stage = {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, nullptr, 0,
                         VK_SHADER_STAGE_COMPUTE_BIT, shader, "main", nullptr};
            pci.layout = layout[push];
            VK_CHECK(vkCreateComputePipelines(device, VK_NULL_HANDLE, 1, &pci, nullptr, &pipeline[push]));
            pipelines.push_back(pipeline[push]);
        }
        std::array<VkDescriptorPoolSize, 3> sizes{{
            {VK_DESCRIPTOR_TYPE_SAMPLER, width}, {VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, 1},
            {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1}}};
        VkDescriptorPoolCreateInfo dpci{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};
        dpci.maxSets = 1; dpci.poolSizeCount = sizes.size(); dpci.pPoolSizes = sizes.data();
        VkDescriptorPool descriptorPool;
        VK_CHECK(vkCreateDescriptorPool(device, &dpci, nullptr, &descriptorPool));
        descriptorPools.push_back(descriptorPool);
        VkDescriptorSetAllocateInfo ai{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};
        ai.descriptorPool = descriptorPool; ai.descriptorSetCount = 1; ai.pSetLayouts = &setLayouts[0];
        VkDescriptorSet set;
        VK_CHECK(vkAllocateDescriptorSets(device, &ai, &set));
        std::array<VkDescriptorImageInfo, 128> infos{};
        for (auto& info : infos) info.sampler = sampler;
        VkDescriptorImageInfo texture{VK_NULL_HANDLE, view, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
        VkDescriptorBufferInfo buffer{output, 0, 8};
        std::array<VkWriteDescriptorSet, 3> writes{};
        for (uint32_t i = 0; i < 3; ++i) {
            writes[i].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
            writes[i].dstSet = set; writes[i].dstBinding = i; writes[i].descriptorCount = 1;
        }
        writes[0].descriptorType = VK_DESCRIPTOR_TYPE_SAMPLER; writes[0].descriptorCount = width;
        writes[0].pImageInfo = infos.data();
        writes[1].descriptorType = VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE; writes[1].pImageInfo = &texture;
        writes[2].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; writes[2].pBufferInfo = &buffer;
        vkUpdateDescriptorSets(device, 3, writes.data(), 0, nullptr);
        VkCommandBuffer setup = beginCommands();
        VkImageMemoryBarrier barrier{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};
        barrier.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED; barrier.newLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
        barrier.dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
        barrier.srcQueueFamilyIndex = barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        barrier.image = image; barrier.subresourceRange = vci.subresourceRange;
        vkCmdPipelineBarrier(setup, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT,
                             0, 0, nullptr, 0, nullptr, 1, &barrier);
        VkClearColorValue zero{};
        vkCmdClearColorImage(setup, image, barrier.newLayout, &zero, 1, &barrier.subresourceRange);
        barrier.oldLayout = barrier.newLayout; barrier.newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
        barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT; barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
        vkCmdPipelineBarrier(setup, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                             0, 0, nullptr, 0, nullptr, 1, &barrier);
        VK_CHECK(vkEndCommandBuffer(setup));
        submitAndWait(setup);
        vkFreeCommandBuffers(device, pool, 1, &setup);
        for (const char* scenario : {"regular", "push-once", "push-each"}) {
            bool regular = std::strcmp(scenario, "regular") == 0;
            bool each = std::strcmp(scenario, "push-each") == 0;
            uint32_t p = regular ? 0 : 1;
            VkCommandBuffer cmd = beginCommands();
            vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline[p]);
            uint32_t constant = 0;
            vkCmdPushConstants(cmd, layout[p], VK_SHADER_STAGE_COMPUTE_BIT, 0, 4, &constant);
            if (regular)
                vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, layout[p], 0, 1, &set, 0, nullptr);
            for (uint32_t i = 0; i < dispatches; ++i) {
                if (!regular && (each || i == 0))
                    vkCmdPushDescriptorSetKHR(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, layout[p], 0, 3, writes.data());
                vkCmdDispatch(cmd, 1, 1, 1);
            }
            VK_CHECK(vkEndCommandBuffer(cmd));
            std::vector<double> submitTimes, totalTimes;
            submitAndWait(cmd);  // warm-up, not measured
            for (uint32_t r = 0; r < repeats; ++r) {
                auto times = submitAndWait(cmd);
                submitTimes.push_back(times.first);
                totalTimes.push_back(times.second);
            }
            vkFreeCommandBuffers(device, pool, 1, &cmd);
            std::sort(submitTimes.begin(), submitTimes.end());
            std::sort(totalTimes.begin(), totalTimes.end());
            double submitUs = submitTimes[repeats / 2] * 1e6 / dispatches;
            double totalUs = totalTimes[repeats / 2] * 1e6 / dispatches;
            std::printf("bench scenario=%s dispatches=%u repeats=%u median_submit_us_per_dispatch=%.3f "
                        "median_total_us_per_dispatch=%.3f\n", scenario, dispatches, repeats, submitUs, totalUs);
            std::fflush(stdout);
        }
        return 0;
    }
};

int main(int argc, char** argv) {
    std::string mode = argc > 2 ? argv[2] : "";
    if (!((mode == "identity" && argc == 3) || (mode == "tess" && argc == 4) ||
          (mode == "bench" && argc == 6))) {
        std::fprintf(stderr, "Usage: probe LIBRARY identity\n"
                             "       probe LIBRARY tess FIXTURE_DIR\n"
                             "       probe LIBRARY bench PUSH_SHADER DISPATCHES REPEATS\n");
        return 2;
    }
    try {
        Probe probe;
        probe.createInstance(argv[1]);
        if (mode == "identity") return 0;
        if (mode == "tess") return probe.tess(argv[3]);
        uint32_t dispatches = static_cast<uint32_t>(std::stoul(argv[4]));
        uint32_t repeats = static_cast<uint32_t>(std::stoul(argv[5]));
        if (dispatches < 1 || dispatches > 200000 || repeats < 1 || repeats > 50)
            throw std::runtime_error("Bench bounds: 1..200000 dispatches, 1..50 repeats");
        return probe.bench(argv[3], dispatches, repeats);
    } catch (const std::exception& error) {
        std::fprintf(stderr, "req104 probe ERROR: %s\n", error.what());
        return 1;
    }
}
