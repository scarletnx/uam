#version 460
// Arithmetic beside interpolation and texture reads: the pairs uam's dual-issue scheduler made.
layout (location = 0) in vec4 inUv;
layout (location = 1) in vec4 inColor;
layout (location = 0) out vec4 outColor;
layout (binding = 0) uniform sampler2D tex;

void main()
{
    vec4 a = texture(tex, inUv.xy) * inColor;
    vec4 b = texture(tex, inUv.zw) + inColor.wzyx;
    outColor = a * b + vec4(inUv.x * inUv.y, inUv.z - inUv.w, 0.5, 1.0);
}
