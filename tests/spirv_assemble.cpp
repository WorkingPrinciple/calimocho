#include <spirv-tools/libspirv.h>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>

int main(int argc, char **argv)
{
    if (argc != 3) {
        std::cerr << "Usage: spirv-assemble INPUT OUTPUT\n";
        return 2;
    }
    std::ifstream input(argv[1]);
    if (!input) {
        std::cerr << "Cannot read input\n";
        return 2;
    }
    const std::string text((std::istreambuf_iterator<char>(input)), {});
    spv_context context = spvContextCreate(SPV_ENV_VULKAN_1_0);
    spv_binary binary = nullptr;
    spv_diagnostic diagnostic = nullptr;
    spv_result_t result = spvTextToBinary(context, text.data(), text.size(),
                                        &binary, &diagnostic);
    if (result == SPV_SUCCESS) {
        spv_const_binary_t words = {binary->code, binary->wordCount};
        result = spvValidate(context, &words, &diagnostic);
    }
    if (result != SPV_SUCCESS) {
        std::cerr << (diagnostic ? diagnostic->error : "SPIR-V validation failed") << '\n';
    } else {
        std::ofstream output(argv[2], std::ios::binary);
        output.write(reinterpret_cast<const char *>(binary->code),
                     binary->wordCount * sizeof(uint32_t));
        if (!output) {
            std::cerr << "Cannot write output\n";
            result = SPV_ERROR_INTERNAL;
        }
    }
    spvDiagnosticDestroy(diagnostic);
    spvBinaryDestroy(binary);
    spvContextDestroy(context);
    return result == SPV_SUCCESS ? 0 : 1;
}
