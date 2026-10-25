"""Generate and compile REQ-104 headless sampler fixtures. Does not execute a GPU."""

import argparse
import json
from pathlib import Path
import subprocess


def shader(mode, width=17):
    split = width // 2 if mode == "mixed" else width
    graphics = mode == "graphics"
    combined = mode == "combined"
    lines = [
        "OpCapability Shader",
        'OpExtension "SPV_KHR_storage_buffer_storage_class"',
        "OpMemoryModel Logical GLSL450",
        f'OpEntryPoint {"Fragment" if graphics else "GLCompute"} %main "main"',
        "OpExecutionMode %main OriginUpperLeft" if graphics else "OpExecutionMode %main LocalSize 1 1 1",
        "OpDecorate %samplers DescriptorSet 0",
        "OpDecorate %samplers Binding 0",
        f"OpDecorate %image DescriptorSet {1 if mode == 'mixed' else 0}",
        "OpDecorate %image Binding 1",
        f"OpDecorate %output DescriptorSet {1 if mode == 'mixed' else 0}",
        "OpDecorate %output Binding 2",
        "OpDecorate %words ArrayStride 4",
        "OpMemberDecorate %outstruct 0 Offset 0",
        "OpDecorate %outstruct Block",
        "OpMemberDecorate %pcstruct 0 Offset 0",
        "OpDecorate %pcstruct Block",
    ]
    if combined:
        lines = [line for line in lines if not line.startswith("OpDecorate %image ")]
    if mode == "mixed":
        lines += ["OpDecorate %samplers2 DescriptorSet 1",
                  "OpDecorate %samplers2 Binding 0"]
    lines += [
        "%void = OpTypeVoid", "%fn = OpTypeFunction %void",
        "%uint = OpTypeInt 32 0", "%float = OpTypeFloat 32",
        "%vec2 = OpTypeVector %float 2", "%vec4 = OpTypeVector %float 4",
        "%sampler = OpTypeSampler",
        "%texture = OpTypeImage %float 2D 0 0 0 1 Unknown",
        "%sampled = OpTypeSampledImage %texture",
    ]
    lines += [f"%u{i} = OpConstant %uint {i}" for i in range(width + 1)]
    lines += [
        "%zero = OpConstant %float 0",
        "%outside = OpConstant %float -1",
        "%coord = OpConstantComposite %vec2 %outside %outside",
        f"%array = OpTypeArray {'%sampled' if combined else '%sampler'} %u{split}",
        "%ptrarray = OpTypePointer UniformConstant %array",
        f"%ptrsampler = OpTypePointer UniformConstant {'%sampled' if combined else '%sampler'}",
        "%ptrimage = OpTypePointer UniformConstant %texture",
        "%words = OpTypeArray %uint %u2",
        "%outstruct = OpTypeStruct %words",
        "%ptrout = OpTypePointer StorageBuffer %outstruct",
        "%ptrword = OpTypePointer StorageBuffer %uint",
        "%pcstruct = OpTypeStruct %uint",
        "%ptrpc = OpTypePointer PushConstant %pcstruct",
        "%ptrindex = OpTypePointer PushConstant %uint",
        "%samplers = OpVariable %ptrarray UniformConstant",
        "%image = OpVariable %ptrimage UniformConstant",
        "%output = OpVariable %ptrout StorageBuffer",
        "%pc = OpVariable %ptrpc PushConstant",
    ]
    if combined:
        lines.remove("%image = OpVariable %ptrimage UniformConstant")
    if mode == "mixed":
        lines += [f"%array2 = OpTypeArray %sampler %u{width - split}",
                  "%ptrarray2 = OpTypePointer UniformConstant %array2",
                  "%samplers2 = OpVariable %ptrarray2 UniformConstant"]
    lines += ["%main = OpFunction %void None %fn", "%entry = OpLabel"]
    if not combined:
        lines.append("%tex = OpLoad %texture %image")
    total = "%u0"
    for i in range(width):
        variable, index = ("%samplers2", i - split) if i >= split else ("%samplers", i)
        lines += [
            f"%p{i} = OpAccessChain %ptrsampler {variable} %u{index}",
        ]
        lines += ([f"%si{i} = OpLoad %sampled %p{i}"] if combined else [
            f"%s{i} = OpLoad %sampler %p{i}", f"%si{i} = OpSampledImage %sampled %tex %s{i}"])
        lines += [
            f"%v{i} = OpImageSampleExplicitLod %vec4 %si{i} %coord Lod %zero",
            f"%r{i} = OpCompositeExtract %float %v{i} 0",
            f"%b{i} = OpConvertFToU %uint %r{i}",
            (f"%bit{i} = OpShiftLeftLogical %uint %b{i} %u{i}" if width == 17
             else f"%bit{i} = OpIMul %uint %b{i} %u{i + 1}"),
            f"%sum{i} = {'OpBitwiseOr' if width == 17 else 'OpIAdd'} %uint {total} %bit{i}",
        ]
        total = f"%sum{i}"
    lines += ["%ip = OpAccessChain %ptrindex %pc %u0",
              "%index = OpLoad %uint %ip",
              "%dst = OpAccessChain %ptrword %output %u0 %index",
              f"OpStore %dst {total}", "OpReturn", "OpFunctionEnd"]
    return "\n".join(lines) + "\n"


VERTEX = """OpCapability Shader
OpMemoryModel Logical GLSL450
OpEntryPoint Vertex %main "main" %position %vertex
OpDecorate %position BuiltIn Position
OpDecorate %vertex BuiltIn VertexIndex
%void = OpTypeVoid
%fn = OpTypeFunction %void
%int = OpTypeInt 32 1
%float = OpTypeFloat 32
%vec4 = OpTypeVector %float 4
%bool = OpTypeBool
%i0 = OpConstant %int 0
%i1 = OpConstant %int 1
%zero = OpConstant %float 0
%one = OpConstant %float 1
%minus = OpConstant %float -1
%three = OpConstant %float 3
%pout = OpTypePointer Output %vec4
%pin = OpTypePointer Input %int
%position = OpVariable %pout Output
%vertex = OpVariable %pin Input
%main = OpFunction %void None %fn
%entry = OpLabel
%v = OpLoad %int %vertex
%first = OpIEqual %bool %v %i0
%second = OpIEqual %bool %v %i1
%x = OpSelect %float %second %three %minus
%y = OpSelect %float %first %three %minus
%pos = OpCompositeConstruct %vec4 %x %y %zero %one
OpStore %position %pos
OpReturn
OpFunctionEnd
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assembler", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--width", type=int, choices=(17, 32, 64, 128), default=17)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    for mode in ("regular", "push", "mixed", "graphics", "combined", "vertex"):
        source = args.output / f"{mode}.spvasm"
        source.write_text(VERTEX if mode == "vertex" else shader(mode, args.width))
        subprocess.run([str(args.assembler.resolve()), str(source),
                        str(source.with_suffix(".spv"))], check=True, timeout=60)
    print(json.dumps({"fixtures": ["regular", "push", "mixed", "graphics", "combined", "vertex"],
                      "samplers_per_stage": args.width, "gpu_submitted": False}))
