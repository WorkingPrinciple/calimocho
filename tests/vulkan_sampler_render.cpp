// REQ-104: headless output oracle, not an advertised-limit or NMS acceptance test.
#define VOLK_IMPLEMENTATION
#include <volk.h>
#include <dlfcn.h>
#include <array>
#include <cstdint>
#include <cstddef>
#include <cstdio>
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

struct Probe {
    void* library = nullptr;
    VkInstance instance = VK_NULL_HANDLE;
    VkPhysicalDevice physical = VK_NULL_HANDLE;
    VkDevice device = VK_NULL_HANDLE;
    VkCommandPool pool = VK_NULL_HANDLE;
    VkDescriptorPool descriptors = VK_NULL_HANDLE;
    VkImage image = VK_NULL_HANDLE;
    VkDeviceMemory imageMemory = VK_NULL_HANDLE;
    VkImageView view = VK_NULL_HANDLE;
    VkBuffer output = VK_NULL_HANDLE;
    VkDeviceMemory outputMemory = VK_NULL_HANDLE;
    std::array<VkSampler, 2> samplers{};
    std::vector<VkDescriptorSetLayout> layouts;
    VkPipelineLayout pipelineLayout = VK_NULL_HANDLE;
    VkShaderModule shader = VK_NULL_HANDLE;
    VkPipeline pipeline = VK_NULL_HANDLE;
    VkFence fence = VK_NULL_HANDLE;
    VkDescriptorUpdateTemplate updateTemplate = VK_NULL_HANDLE;
    VkRenderPass renderPass = VK_NULL_HANDLE;
    VkFramebuffer framebuffer = VK_NULL_HANDLE;
    VkShaderModule vertex = VK_NULL_HANDLE;

    ~Probe() {
        // A failed wait is not permission to destroy objects still used by a queue.
        if (device) {
            VkResult idle = vkDeviceWaitIdle(device);
            if (idle != VK_SUCCESS)
                std::fprintf(stderr, "cleanup vkDeviceWaitIdle: %d\n", idle);
            if (fence) vkDestroyFence(device, fence, nullptr);
            if (pool) vkDestroyCommandPool(device, pool, nullptr);
            if (updateTemplate) vkDestroyDescriptorUpdateTemplate(device, updateTemplate, nullptr);
            if (pipeline) vkDestroyPipeline(device, pipeline, nullptr);
            if (framebuffer) vkDestroyFramebuffer(device, framebuffer, nullptr);
            if (renderPass) vkDestroyRenderPass(device, renderPass, nullptr);
            if (vertex) vkDestroyShaderModule(device, vertex, nullptr);
            if (shader) vkDestroyShaderModule(device, shader, nullptr);
            if (pipelineLayout) vkDestroyPipelineLayout(device, pipelineLayout, nullptr);
            if (descriptors) vkDestroyDescriptorPool(device, descriptors, nullptr);
            for (auto layout : layouts) vkDestroyDescriptorSetLayout(device, layout, nullptr);
            for (auto sampler : samplers) if (sampler) vkDestroySampler(device, sampler, nullptr);
            if (view) vkDestroyImageView(device, view, nullptr);
            if (image) vkDestroyImage(device, image, nullptr);
            if (imageMemory) vkFreeMemory(device, imageMemory, nullptr);
            if (output) vkDestroyBuffer(device, output, nullptr);
            if (outputMemory) vkFreeMemory(device, outputMemory, nullptr);
            vkDestroyDevice(device, nullptr);
        }
        if (instance) vkDestroyInstance(instance, nullptr);
        if (library) dlclose(library);
    }

    uint32_t memoryType(uint32_t mask, VkMemoryPropertyFlags flags) {
        VkPhysicalDeviceMemoryProperties memory{};
        vkGetPhysicalDeviceMemoryProperties(physical, &memory);
        for (uint32_t i = 0; i < memory.memoryTypeCount; ++i)
            if ((mask & (1u << i)) && (memory.memoryTypes[i].propertyFlags & flags) == flags)
                return i;
        throw std::runtime_error("No required memory type");
    }

    int run(const char* libraryPath, const std::string& mode,
            const char* shaderPath, bool exercise) {
        library = dlopen(libraryPath, RTLD_NOW | RTLD_LOCAL);
        if (!library) throw std::runtime_error(dlerror());
        auto get = reinterpret_cast<PFN_vkGetInstanceProcAddr>(
            dlsym(library, "vkGetInstanceProcAddr"));
        if (!get) throw std::runtime_error("Missing vkGetInstanceProcAddr");
        volkInitializeCustom(get);
        VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};
        app.pApplicationName = "REQ104 sampler output oracle";
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
        VkPhysicalDeviceProperties properties{};
        vkGetPhysicalDeviceProperties(physical, &properties);
        std::printf("ordinary_limit=%u mode=%s\n",
                    properties.limits.maxPerStageDescriptorSamplers, mode.c_str());
        if (properties.limits.maxPerStageDescriptorSamplers < 17 && !exercise) {
            std::fprintf(stderr, "SKIP: 17 exceeds advertised limit; no logical device or GPU work. "
                                 "Explicit --exercise-unsupported is diagnostic only.\n");
            return 77;
        }
        bool push = mode != "regular";
        bool graphics = mode == "graphics";
        VkShaderStageFlags stage = graphics ? VK_SHADER_STAGE_FRAGMENT_BIT : VK_SHADER_STAGE_COMPUTE_BIT;
        VkPipelineBindPoint bindPoint = graphics ? VK_PIPELINE_BIND_POINT_GRAPHICS : VK_PIPELINE_BIND_POINT_COMPUTE;
        vkGetPhysicalDeviceQueueFamilyProperties(physical, &count, nullptr);
        std::vector<VkQueueFamilyProperties> families(count);
        vkGetPhysicalDeviceQueueFamilyProperties(physical, &count, families.data());
        uint32_t family = 0;
        while (family < count && !(families[family].queueFlags &
               (graphics ? VK_QUEUE_GRAPHICS_BIT : VK_QUEUE_COMPUTE_BIT))) ++family;
        if (family == count) throw std::runtime_error("No compute queue");
        float priority = 1;
        VkDeviceQueueCreateInfo qci{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
        qci.queueFamilyIndex = family; qci.queueCount = 1; qci.pQueuePriorities = &priority;
        const char* extension = VK_KHR_PUSH_DESCRIPTOR_EXTENSION_NAME;
        VkDeviceCreateInfo dci{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
        dci.queueCreateInfoCount = 1; dci.pQueueCreateInfos = &qci;
        dci.enabledExtensionCount = push ? 1 : 0;
        dci.ppEnabledExtensionNames = push ? &extension : nullptr;
        VkPhysicalDeviceFeatures features{};
        if (graphics) {
            vkGetPhysicalDeviceFeatures(physical, &features);
            if (!features.fragmentStoresAndAtomics)
                throw std::runtime_error("Fragment storage writes unavailable");
            features = {};
            features.fragmentStoresAndAtomics = VK_TRUE;
            dci.pEnabledFeatures = &features;
        }
        VK_CHECK(vkCreateDevice(physical, &dci, nullptr, &device));
        volkLoadDevice(device);
        if (push && !vkCmdPushDescriptorSetKHR)
            throw std::runtime_error("Push descriptor entrypoint unavailable");
        VkQueue queue;
        vkGetDeviceQueue(device, family, 0, &queue);
        VkBufferCreateInfo bci{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
        bci.size = 8; bci.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT;
        VK_CHECK(vkCreateBuffer(device, &bci, nullptr, &output));
        VkMemoryRequirements req{};
        vkGetBufferMemoryRequirements(device, output, &req);
        VkMemoryAllocateInfo mai{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
        mai.allocationSize = req.size;
        mai.memoryTypeIndex = memoryType(req.memoryTypeBits,
            VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
        VK_CHECK(vkAllocateMemory(device, &mai, nullptr, &outputMemory));
        VK_CHECK(vkBindBufferMemory(device, output, outputMemory, 0));
        void* mapped = nullptr;
        VK_CHECK(vkMapMemory(device, outputMemory, 0, 8, 0, &mapped));
        std::memset(mapped, 0xff, 8);
        vkUnmapMemory(device, outputMemory);
        VkImageCreateInfo im{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
        im.imageType = VK_IMAGE_TYPE_2D; im.format = VK_FORMAT_R32_SFLOAT;
        im.extent = {1, 1, 1}; im.mipLevels = 1; im.arrayLayers = 1;
        im.samples = VK_SAMPLE_COUNT_1_BIT; im.tiling = VK_IMAGE_TILING_OPTIMAL;
        im.usage = VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT;
        VK_CHECK(vkCreateImage(device, &im, nullptr, &image));
        vkGetImageMemoryRequirements(device, image, &req);
        mai.allocationSize = req.size; mai.memoryTypeIndex = memoryType(req.memoryTypeBits, 0);
        VK_CHECK(vkAllocateMemory(device, &mai, nullptr, &imageMemory));
        VK_CHECK(vkBindImageMemory(device, image, imageMemory, 0));
        VkImageViewCreateInfo vci{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};
        vci.image = image; vci.viewType = VK_IMAGE_VIEW_TYPE_2D; vci.format = im.format;
        vci.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
        VK_CHECK(vkCreateImageView(device, &vci, nullptr, &view));
        for (uint32_t i = 0; i < 2; ++i) {
            VkSamplerCreateInfo sci{VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO};
            sci.magFilter = sci.minFilter = VK_FILTER_NEAREST;
            sci.mipmapMode = VK_SAMPLER_MIPMAP_MODE_NEAREST;
            sci.addressModeU = sci.addressModeV = sci.addressModeW =
                i ? VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_BORDER : VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
            sci.borderColor = VK_BORDER_COLOR_FLOAT_OPAQUE_WHITE;
            VK_CHECK(vkCreateSampler(device, &sci, nullptr, &samplers[i]));
        }
        uint32_t setCount = mode == "mixed" ? 2 : 1;
        layouts.resize(setCount);
        for (uint32_t s = 0; s < setCount; ++s) {
            uint32_t samplerCount = mode == "mixed" ? (s ? 9 : 8) : 17;
            std::array<VkDescriptorSetLayoutBinding, 3> bindings{{
                {0, VK_DESCRIPTOR_TYPE_SAMPLER, samplerCount, stage, nullptr},
                {1, VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, 1, stage, nullptr},
                {2, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1, stage, nullptr}}};
            VkDescriptorSetLayoutCreateInfo lci{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
            lci.flags = push && s == 0 ? VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR : 0;
            lci.bindingCount = mode == "mixed" && s == 0 ? 1 : 3;
            lci.pBindings = bindings.data();
            VK_CHECK(vkCreateDescriptorSetLayout(device, &lci, nullptr, &layouts[s]));
        }
        VkPushConstantRange range{stage, 0, 4};
        VkPipelineLayoutCreateInfo plci{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
        plci.setLayoutCount = setCount; plci.pSetLayouts = layouts.data();
        plci.pushConstantRangeCount = 1; plci.pPushConstantRanges = &range;
        VK_CHECK(vkCreatePipelineLayout(device, &plci, nullptr, &pipelineLayout));
        std::ifstream input(shaderPath, std::ios::binary | std::ios::ate);
        if (!input) throw std::runtime_error("Cannot open shader");
        auto length = input.tellg();
        if (length <= 0 || length % 4) throw std::runtime_error("Invalid SPIR-V size");
        std::vector<uint32_t> code(static_cast<size_t>(length) / 4);
        input.seekg(0); input.read(reinterpret_cast<char*>(code.data()), length);
        if (!input) throw std::runtime_error("Cannot read shader");
        VkShaderModuleCreateInfo smci{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};
        smci.codeSize = static_cast<size_t>(length); smci.pCode = code.data();
        VK_CHECK(vkCreateShaderModule(device, &smci, nullptr, &shader));
        VkComputePipelineCreateInfo pci{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};
        pci.stage = {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, nullptr, 0,
                     VK_SHADER_STAGE_COMPUTE_BIT, shader, "main", nullptr};
        pci.layout = pipelineLayout;
        if (!graphics) {
            VK_CHECK(vkCreateComputePipelines(device, VK_NULL_HANDLE, 1, &pci, nullptr, &pipeline));
        } else {
            std::string path(shaderPath);
            path = path.substr(0, path.find_last_of('/') + 1) + "vertex.spv";
            std::ifstream vertexInput(path, std::ios::binary | std::ios::ate);
            if (!vertexInput) throw std::runtime_error("Cannot open vertex shader");
            auto bytes = vertexInput.tellg();
            if (bytes <= 0 || bytes % 4) throw std::runtime_error("Invalid vertex shader size");
            std::vector<uint32_t> vertexCode(static_cast<size_t>(bytes) / 4);
            vertexInput.seekg(0); vertexInput.read(reinterpret_cast<char*>(vertexCode.data()), bytes);
            if (!vertexInput) throw std::runtime_error("Cannot read vertex shader");
            smci.codeSize = static_cast<size_t>(bytes); smci.pCode = vertexCode.data();
            VK_CHECK(vkCreateShaderModule(device, &smci, nullptr, &vertex));
            VkSubpassDescription subpass{};
            subpass.pipelineBindPoint = bindPoint;
            VkRenderPassCreateInfo rpci{VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO};
            rpci.subpassCount = 1; rpci.pSubpasses = &subpass;
            VK_CHECK(vkCreateRenderPass(device, &rpci, nullptr, &renderPass));
            VkFramebufferCreateInfo fbci{VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO};
            fbci.renderPass = renderPass; fbci.width = fbci.height = fbci.layers = 1;
            VK_CHECK(vkCreateFramebuffer(device, &fbci, nullptr, &framebuffer));
            std::array<VkPipelineShaderStageCreateInfo, 2> stages{{
                {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, nullptr, 0,
                 VK_SHADER_STAGE_VERTEX_BIT, vertex, "main", nullptr},
                {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, nullptr, 0,
                 VK_SHADER_STAGE_FRAGMENT_BIT, shader, "main", nullptr}}};
            VkPipelineVertexInputStateCreateInfo vi{VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};
            VkPipelineInputAssemblyStateCreateInfo ia{VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO};
            ia.topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
            VkViewport viewport{0, 0, 1, 1, 0, 1};
            VkRect2D scissor{{0, 0}, {1, 1}};
            VkPipelineViewportStateCreateInfo vp{VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO};
            vp.viewportCount = vp.scissorCount = 1; vp.pViewports = &viewport; vp.pScissors = &scissor;
            VkPipelineRasterizationStateCreateInfo rs{VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO};
            rs.polygonMode = VK_POLYGON_MODE_FILL; rs.lineWidth = 1;
            VkPipelineMultisampleStateCreateInfo ms{VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO};
            ms.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;
            VkPipelineColorBlendStateCreateInfo blend{VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO};
            VkGraphicsPipelineCreateInfo gpci{VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO};
            gpci.stageCount = 2; gpci.pStages = stages.data(); gpci.pVertexInputState = &vi;
            gpci.pInputAssemblyState = &ia; gpci.pViewportState = &vp; gpci.pRasterizationState = &rs;
            gpci.pMultisampleState = &ms; gpci.pColorBlendState = &blend;
            gpci.layout = pipelineLayout; gpci.renderPass = renderPass;
            VK_CHECK(vkCreateGraphicsPipelines(device, VK_NULL_HANDLE, 1, &gpci, nullptr, &pipeline));
        }
        struct TemplateData {
            std::array<VkDescriptorImageInfo, 17> samplers;
            VkDescriptorImageInfo texture;
            VkDescriptorBufferInfo buffer;
        };
        if (mode == "template") {
            std::array<VkDescriptorUpdateTemplateEntry, 3> entries{{
                {0, 0, 17, VK_DESCRIPTOR_TYPE_SAMPLER, offsetof(TemplateData, samplers), sizeof(VkDescriptorImageInfo)},
                {1, 0, 1, VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, offsetof(TemplateData, texture), sizeof(VkDescriptorImageInfo)},
                {2, 0, 1, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, offsetof(TemplateData, buffer), sizeof(VkDescriptorBufferInfo)}}};
            VkDescriptorUpdateTemplateCreateInfo ti{VK_STRUCTURE_TYPE_DESCRIPTOR_UPDATE_TEMPLATE_CREATE_INFO};
            ti.descriptorUpdateEntryCount = 3; ti.pDescriptorUpdateEntries = entries.data();
            ti.templateType = VK_DESCRIPTOR_UPDATE_TEMPLATE_TYPE_PUSH_DESCRIPTORS_KHR;
            ti.pipelineBindPoint = bindPoint; ti.pipelineLayout = pipelineLayout;
            VK_CHECK(vkCreateDescriptorUpdateTemplate(device, &ti, nullptr, &updateTemplate));
            if (!vkCmdPushDescriptorSetWithTemplateKHR) throw std::runtime_error("No push template function");
        }
        std::array<VkDescriptorPoolSize, 3> sizes{{
            {VK_DESCRIPTOR_TYPE_SAMPLER, 34}, {VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, 2},
            {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 2}}};
        VkDescriptorPoolCreateInfo dpci{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};
        dpci.maxSets = 2; dpci.poolSizeCount = 3; dpci.pPoolSizes = sizes.data();
        VK_CHECK(vkCreateDescriptorPool(device, &dpci, nullptr, &descriptors));
        std::array<std::array<VkDescriptorSet, 2>, 2> sets{};
        // Regular descriptors use separate immutable sets per dispatch. Updating a
        // bound ordinary set in place would not be a valid Vulkan lifetime test.
        for (uint32_t pass = 0; pass < 2; ++pass) {
            uint32_t s = mode == "mixed" ? 1 : 0;
            if (push && mode != "mixed") continue;
            VkDescriptorSetAllocateInfo ai{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};
            ai.descriptorPool = descriptors; ai.descriptorSetCount = 1; ai.pSetLayouts = &layouts[s];
            VK_CHECK(vkAllocateDescriptorSets(device, &ai, &sets[pass][s]));
        }
        VkCommandPoolCreateInfo cpci{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};
        cpci.queueFamilyIndex = family;
        VK_CHECK(vkCreateCommandPool(device, &cpci, nullptr, &pool));
        VkCommandBufferAllocateInfo cai{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
        cai.commandPool = pool; cai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY; cai.commandBufferCount = 1;
        VkCommandBuffer cmd;
        VK_CHECK(vkAllocateCommandBuffers(device, &cai, &cmd));
        VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
        VK_CHECK(vkBeginCommandBuffer(cmd, &begin));
        VkImageMemoryBarrier barrier{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};
        barrier.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED; barrier.newLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
        barrier.dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
        barrier.srcQueueFamilyIndex = barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        barrier.image = image; barrier.subresourceRange = vci.subresourceRange;
        vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT,
                             0, 0, nullptr, 0, nullptr, 1, &barrier);
        VkClearColorValue black{};
        vkCmdClearColorImage(cmd, image, barrier.newLayout, &black, 1, &barrier.subresourceRange);
        barrier.oldLayout = barrier.newLayout; barrier.newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
        barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT; barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
        VkPipelineStageFlags pipelineStage = graphics ? VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT : VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT;
        vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT, pipelineStage,
                             0, 0, nullptr, 0, nullptr, 1, &barrier);
        if (graphics) {
            VkRenderPassBeginInfo ri{VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO};
            ri.renderPass = renderPass; ri.framebuffer = framebuffer;
            ri.renderArea = {{0, 0}, {1, 1}};
            vkCmdBeginRenderPass(cmd, &ri, VK_SUBPASS_CONTENTS_INLINE);
        }
        vkCmdBindPipeline(cmd, bindPoint, pipeline);
        for (uint32_t pass = 0; pass < 2; ++pass) {
            for (uint32_t s = 0; s < setCount; ++s) {
                uint32_t n = mode == "mixed" ? (s ? 9 : 8) : 17;
                uint32_t offset = mode == "mixed" && s ? 8 : 0;
                std::array<VkDescriptorImageInfo, 17> infos{};
                for (uint32_t i = 0; i < n; ++i) infos[i].sampler = samplers[(i + offset + pass) % 2];
                VkDescriptorImageInfo texture{VK_NULL_HANDLE, view, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
                VkDescriptorBufferInfo buffer{output, 0, 8};
                std::array<VkWriteDescriptorSet, 3> writes{};
                for (uint32_t i = 0; i < 3; ++i) {
                    writes[i].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
                    writes[i].dstBinding = i; writes[i].descriptorCount = 1;
                    writes[i].dstSet = sets[pass][s];
                }
                writes[0].descriptorType = VK_DESCRIPTOR_TYPE_SAMPLER;
                writes[0].descriptorCount = n; writes[0].pImageInfo = infos.data();
                writes[1].descriptorType = VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE; writes[1].pImageInfo = &texture;
                writes[2].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; writes[2].pBufferInfo = &buffer;
                uint32_t writeCount = mode == "mixed" && s == 0 ? 1 : 3;
                if (push && s == 0) {
                    if (mode == "template") {
                        TemplateData data{infos, texture, buffer};
                        vkCmdPushDescriptorSetWithTemplateKHR(cmd, updateTemplate, pipelineLayout, s, &data);
                    } else if (mode == "partial" && pass == 1) {
                        // REQ-104: partial writes must preserve the image, buffer,
                        // and sampler elements not included in each write.
                        for (uint32_t i = 0; i < n; ++i) {
                            writes[0].dstArrayElement = i; writes[0].descriptorCount = 1;
                            writes[0].pImageInfo = &infos[i];
                            vkCmdPushDescriptorSetKHR(cmd, bindPoint, pipelineLayout, s, 1, writes.data());
                        }
                    } else vkCmdPushDescriptorSetKHR(cmd, bindPoint, pipelineLayout,
                                                    s, writeCount, writes.data());
                }
                else {
                    vkUpdateDescriptorSets(device, writeCount, writes.data(), 0, nullptr);
                    vkCmdBindDescriptorSets(cmd, bindPoint, pipelineLayout,
                                            s, 1, &sets[pass][s], 0, nullptr);
                }
            }
            vkCmdPushConstants(cmd, pipelineLayout, stage, 0, 4, &pass);
            if (graphics) vkCmdDraw(cmd, 3, 1, 0, 0);
            else vkCmdDispatch(cmd, 1, 1, 1);
        }
        if (graphics) vkCmdEndRenderPass(cmd);
        VkMemoryBarrier host{VK_STRUCTURE_TYPE_MEMORY_BARRIER};
        host.srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT; host.dstAccessMask = VK_ACCESS_HOST_READ_BIT;
        vkCmdPipelineBarrier(cmd, pipelineStage, VK_PIPELINE_STAGE_HOST_BIT,
                             0, 1, &host, 0, nullptr, 0, nullptr);
        VK_CHECK(vkEndCommandBuffer(cmd));
        VkFenceCreateInfo fci{VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
        VK_CHECK(vkCreateFence(device, &fci, nullptr, &fence));
        VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};
        submit.commandBufferCount = 1; submit.pCommandBuffers = &cmd;
        for (uint32_t replay = 0; replay < 2; ++replay) {
            VK_CHECK(vkQueueSubmit(queue, 1, &submit, fence));
            VK_CHECK(vkWaitForFences(device, 1, &fence, VK_TRUE, 30000000000ull));
            VK_CHECK(vkMapMemory(device, outputMemory, 0, 8, 0, &mapped));
            std::array<uint32_t, 2> observed{};
            std::memcpy(observed.data(), mapped, 8);
            std::memset(mapped, 0xff, 8);
            vkUnmapMemory(device, outputMemory);
            // REQ-104: every sampler contributes one bit; a later push must not
            // alter the first dispatch, including after command-buffer replay.
            bool correct = observed[0] == 0xaaaa && observed[1] == 0x15555;
            std::printf("replay=%u observed=[0x%x,0x%x] expected=[0xaaaa,0x15555] result=%s "
                        "advertised_support=%s\n", replay, observed[0], observed[1],
                        correct ? "PASS" : "FAIL",
                        properties.limits.maxPerStageDescriptorSamplers >= 17 ? "true" : "false");
            if (!correct) return 1;
            VK_CHECK(vkResetFences(device, 1, &fence));
        }
        return 0;
    }
};

int main(int argc, char** argv) {
    if ((argc != 4 && argc != 5) ||
        (std::string(argv[2]) != "regular" && std::string(argv[2]) != "push" &&
         std::string(argv[2]) != "mixed" && std::string(argv[2]) != "template" &&
         std::string(argv[2]) != "partial" && std::string(argv[2]) != "graphics") ||
        (argc == 5 && std::string(argv[4]) != "--exercise-unsupported")) {
        std::fprintf(stderr, "Usage: probe LIBRARY regular|push|mixed|template|partial|graphics SHADER "
                             "[--exercise-unsupported]\n");
        return 2;
    }
    try {
        Probe probe;
        return probe.run(argv[1], argv[2], argv[3], argc == 5);
    } catch (const std::exception& error) {
        std::fprintf(stderr, "sampler probe ERROR: %s\n", error.what());
        return 1;
    }
}
