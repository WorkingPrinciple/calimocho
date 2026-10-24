/* SPDX-License-Identifier: LGPL-2.1-or-later */
#define SAMPLER_COUNT 17

static uint32_t sampler_memory_type(VkPhysicalDevice physical, uint32_t bits,
                                    VkMemoryPropertyFlags flags)
{
    VkPhysicalDeviceMemoryProperties memory;
    vkGetPhysicalDeviceMemoryProperties(physical, &memory);
    for (uint32_t i = 0; i < memory.memoryTypeCount; ++i)
        if ((bits & (1u << i)) && (memory.memoryTypes[i].propertyFlags & flags) == flags)
            return i;
    return UINT32_MAX;
}

static int probe_sampler_capacity(VkPhysicalDevice physical, VkDevice device, VkQueue queue,
                                 uint32_t family, const char *shader_path)
{
    VkShaderModule shader = VK_NULL_HANDLE;
    VkDescriptorSetLayout layout = VK_NULL_HANDLE;
    VkPipelineLayout pipeline_layout = VK_NULL_HANDLE;
    VkPipeline pipeline = VK_NULL_HANDLE;
    VkDescriptorPool descriptors = VK_NULL_HANDLE;
    VkDescriptorSet set;
    VkImage image = VK_NULL_HANDLE;
    VkImageView view = VK_NULL_HANDLE;
    VkDeviceMemory image_memory = VK_NULL_HANDLE, output_memory = VK_NULL_HANDLE;
    VkBuffer output = VK_NULL_HANDLE;
    VkSampler samplers[SAMPLER_COUNT] = {0};
    VkCommandPool pool = VK_NULL_HANDLE;
    VkCommandBuffer command;
    VkFence fence = VK_NULL_HANDLE;
    VkResult status;
    VkMemoryRequirements requirements;
    VkPhysicalDeviceProperties properties;
    uint32_t *words = NULL;
    FILE *file = NULL;
    void *mapped = NULL;
    int result = 1;
#define SAMPLER_CHECK(call) do { \
    status = (call); \
    printf("sampler17 %s VkResult=%d\n", #call, status); \
    if (status != VK_SUCCESS) goto done; \
} while (0)

    vkGetPhysicalDeviceProperties(physical, &properties);
    if (properties.limits.maxPerStageDescriptorSamplers < SAMPLER_COUNT ||
        properties.limits.maxDescriptorSetSamplers < SAMPLER_COUNT ||
        properties.limits.maxPerStageDescriptorSampledImages < SAMPLER_COUNT)
    {
        printf("sampler17 ERROR advertised capacity insufficient\n");
        goto done;
    }
    file = fopen(shader_path, "rb");
    if (!file || fseek(file, 0, SEEK_END)) goto file_error;
    long size = ftell(file);
    if (size < 20 || size > 1024 * 1024 || size % 4 || fseek(file, 0, SEEK_SET))
        goto file_error;
    words = malloc((size_t)size);
    if (!words || fread(words, 1, (size_t)size, file) != (size_t)size) goto file_error;
    if (fclose(file)) { file = NULL; goto file_error; }
    file = NULL;
    VkShaderModuleCreateInfo shader_info = {.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
        .codeSize = (size_t)size, .pCode = words};
    SAMPLER_CHECK(vkCreateShaderModule(device, &shader_info, NULL, &shader));
    VkDescriptorSetLayoutBinding bindings[2] = {
        {.binding = 0, .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,
         .descriptorCount = SAMPLER_COUNT, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT},
        {.binding = 1, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
         .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT}};
    VkDescriptorSetLayoutCreateInfo layout_info = {
        .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
        .bindingCount = 2, .pBindings = bindings};
    SAMPLER_CHECK(vkCreateDescriptorSetLayout(device, &layout_info, NULL, &layout));
    VkPipelineLayoutCreateInfo pipeline_layout_info = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .setLayoutCount = 1, .pSetLayouts = &layout};
    SAMPLER_CHECK(vkCreatePipelineLayout(device, &pipeline_layout_info, NULL, &pipeline_layout));
    VkComputePipelineCreateInfo pipeline_info = {
        .sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,
        .stage = {.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                  .stage = VK_SHADER_STAGE_COMPUTE_BIT, .module = shader, .pName = "main"},
        .layout = pipeline_layout};
    SAMPLER_CHECK(vkCreateComputePipelines(device, VK_NULL_HANDLE, 1, &pipeline_info, NULL, &pipeline));
    VkImageCreateInfo image_info = {.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,
        .imageType = VK_IMAGE_TYPE_2D, .format = VK_FORMAT_R8G8B8A8_UNORM,
        .extent = {1, 1, 1}, .mipLevels = 1, .arrayLayers = 1, .samples = VK_SAMPLE_COUNT_1_BIT,
        .tiling = VK_IMAGE_TILING_OPTIMAL,
        .usage = VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT,
        .sharingMode = VK_SHARING_MODE_EXCLUSIVE};
    SAMPLER_CHECK(vkCreateImage(device, &image_info, NULL, &image));
    vkGetImageMemoryRequirements(device, image, &requirements);
    uint32_t type = sampler_memory_type(physical, requirements.memoryTypeBits, 0);
    if (type == UINT32_MAX) goto memory_error;
    VkMemoryAllocateInfo allocation = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .allocationSize = requirements.size, .memoryTypeIndex = type};
    SAMPLER_CHECK(vkAllocateMemory(device, &allocation, NULL, &image_memory));
    SAMPLER_CHECK(vkBindImageMemory(device, image, image_memory, 0));
    VkImageViewCreateInfo view_info = {.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,
        .image = image, .viewType = VK_IMAGE_VIEW_TYPE_2D, .format = image_info.format,
        .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    SAMPLER_CHECK(vkCreateImageView(device, &view_info, NULL, &view));
    VkBufferCreateInfo buffer_info = {.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
        .size = SAMPLER_COUNT * 4 * sizeof(float), .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
        .sharingMode = VK_SHARING_MODE_EXCLUSIVE};
    SAMPLER_CHECK(vkCreateBuffer(device, &buffer_info, NULL, &output));
    vkGetBufferMemoryRequirements(device, output, &requirements);
    type = sampler_memory_type(physical, requirements.memoryTypeBits,
                              VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
    if (type == UINT32_MAX) goto memory_error;
    allocation.allocationSize = requirements.size;
    allocation.memoryTypeIndex = type;
    SAMPLER_CHECK(vkAllocateMemory(device, &allocation, NULL, &output_memory));
    SAMPLER_CHECK(vkBindBufferMemory(device, output, output_memory, 0));
    SAMPLER_CHECK(vkMapMemory(device, output_memory, 0, buffer_info.size, 0, &mapped));
    memset(mapped, 0xcd, (size_t)buffer_info.size);
    vkUnmapMemory(device, output_memory);
    mapped = NULL;
    VkDescriptorImageInfo images[SAMPLER_COUNT];
    for (uint32_t i = 0; i < SAMPLER_COUNT; ++i)
    {
        VkSamplerCreateInfo info = {.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO,
            .magFilter = VK_FILTER_NEAREST, .minFilter = VK_FILTER_NEAREST,
            .mipmapMode = VK_SAMPLER_MIPMAP_MODE_NEAREST,
            .addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_BORDER,
            .addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_BORDER,
            .addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_BORDER,
            .borderColor = i % 2 ? VK_BORDER_COLOR_FLOAT_OPAQUE_BLACK : VK_BORDER_COLOR_FLOAT_OPAQUE_WHITE};
        SAMPLER_CHECK(vkCreateSampler(device, &info, NULL, &samplers[i]));
        images[i] = (VkDescriptorImageInfo){samplers[i], view, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    }
    VkDescriptorPoolSize sizes[2] = {
        {VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, SAMPLER_COUNT},
        {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1}};
    VkDescriptorPoolCreateInfo descriptor_info = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,
        .maxSets = 1, .poolSizeCount = 2, .pPoolSizes = sizes};
    SAMPLER_CHECK(vkCreateDescriptorPool(device, &descriptor_info, NULL, &descriptors));
    VkDescriptorSetAllocateInfo set_info = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,
        .descriptorPool = descriptors, .descriptorSetCount = 1, .pSetLayouts = &layout};
    SAMPLER_CHECK(vkAllocateDescriptorSets(device, &set_info, &set));
    VkDescriptorBufferInfo output_info = {output, 0, buffer_info.size};
    VkWriteDescriptorSet writes[2] = {
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstSet = set, .dstBinding = 0,
         .descriptorCount = SAMPLER_COUNT, .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,
         .pImageInfo = images},
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstSet = set, .dstBinding = 1,
         .descriptorCount = 1, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
         .pBufferInfo = &output_info}};
    vkUpdateDescriptorSets(device, 2, writes, 0, NULL);
    VkCommandPoolCreateInfo pool_info = {.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
        .queueFamilyIndex = family};
    SAMPLER_CHECK(vkCreateCommandPool(device, &pool_info, NULL, &pool));
    VkCommandBufferAllocateInfo command_info = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
        .commandPool = pool, .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1};
    SAMPLER_CHECK(vkAllocateCommandBuffers(device, &command_info, &command));
    VkCommandBufferBeginInfo begin = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
    SAMPLER_CHECK(vkBeginCommandBuffer(command, &begin));
    VkImageMemoryBarrier image_barrier = {.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
        .dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT,
        .oldLayout = VK_IMAGE_LAYOUT_UNDEFINED, .newLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED, .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .image = image, .subresourceRange = view_info.subresourceRange};
    vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT,
                         0, 0, NULL, 0, NULL, 1, &image_barrier);
    VkClearColorValue clear = {.float32 = {0.25f, 0.25f, 0.25f, 1.0f}};
    vkCmdClearColorImage(command, image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                        &clear, 1, &view_info.subresourceRange);
    image_barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
    image_barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
    image_barrier.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    image_barrier.newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                         0, 0, NULL, 0, NULL, 1, &image_barrier);
    vkCmdBindPipeline(command, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline);
    vkCmdBindDescriptorSets(command, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline_layout, 0, 1, &set, 0, NULL);
    vkCmdDispatch(command, 1, 1, 1);
    VkBufferMemoryBarrier output_barrier = {.sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER,
        .srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT, .dstAccessMask = VK_ACCESS_HOST_READ_BIT,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED, .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .buffer = output, .size = VK_WHOLE_SIZE};
    vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_HOST_BIT,
                         0, 0, NULL, 1, &output_barrier, 0, NULL);
    SAMPLER_CHECK(vkEndCommandBuffer(command));
    VkFenceCreateInfo fence_info = {.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
    SAMPLER_CHECK(vkCreateFence(device, &fence_info, NULL, &fence));
    VkSubmitInfo submit = {.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO,
        .commandBufferCount = 1, .pCommandBuffers = &command};
    SAMPLER_CHECK(vkQueueSubmit(queue, 1, &submit, fence));
    SAMPLER_CHECK(vkWaitForFences(device, 1, &fence, VK_TRUE, 10000000000ULL));
    SAMPLER_CHECK(vkMapMemory(device, output_memory, 0, buffer_info.size, 0, &mapped));
    float *pixels = mapped;
    for (uint32_t i = 0; i < SAMPLER_COUNT; ++i)
        for (uint32_t c = 0; c < 4; ++c)
            if (pixels[i * 4 + c] != (c == 3 || !(i % 2) ? 1.0f : 0.0f))
            {
                printf("sampler17 ERROR slot=%u channel=%u actual=%f\n", i, c, pixels[i * 4 + c]);
                goto done;
            }
    printf("sampler17 dispatched=1 sampled_slots=17 exact_border_readbacks=17 result=0\n");
    result = 0;
    goto done;
file_error:
    printf("sampler17 ERROR cannot read SPIR-V fixture\n");
    goto done;
memory_error:
    printf("sampler17 ERROR no compatible memory type\n");
done:
    if (mapped) vkUnmapMemory(device, output_memory);
    if (file) fclose(file);
    free(words);
    if (pool) {
        VkResult idle = vkDeviceWaitIdle(device);
        if (idle != VK_SUCCESS) { printf("sampler17 cleanup VkResult=%d\n", idle); result = 1; }
    }
    if (fence) vkDestroyFence(device, fence, NULL);
    if (pool) vkDestroyCommandPool(device, pool, NULL);
    if (descriptors) vkDestroyDescriptorPool(device, descriptors, NULL);
    for (uint32_t i = 0; i < SAMPLER_COUNT; ++i)
        if (samplers[i]) vkDestroySampler(device, samplers[i], NULL);
    if (output) vkDestroyBuffer(device, output, NULL);
    if (output_memory) vkFreeMemory(device, output_memory, NULL);
    if (view) vkDestroyImageView(device, view, NULL);
    if (image) vkDestroyImage(device, image, NULL);
    if (image_memory) vkFreeMemory(device, image_memory, NULL);
    if (pipeline) vkDestroyPipeline(device, pipeline, NULL);
    if (pipeline_layout) vkDestroyPipelineLayout(device, pipeline_layout, NULL);
    if (layout) vkDestroyDescriptorSetLayout(device, layout, NULL);
    if (shader) vkDestroyShaderModule(device, shader, NULL);
    return result;
#undef SAMPLER_CHECK
}
