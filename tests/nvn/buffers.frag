#version 460

// A fragment program's uniform block and storage buffer, for tests/nvn/check.py.

layout (location = 0) out vec4 color;

layout (std140, binding = 0) uniform Block
{
    vec4 tint;
} block;

layout (std430, binding = 0) readonly buffer In
{
    vec4 values[];
};

void main()
{
    color = values[uint(gl_FragCoord.x)] * block.tint;
}
