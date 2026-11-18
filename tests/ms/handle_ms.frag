#version 460
#extension GL_ARB_bindless_texture : require
// A multisample fetch through a bindless handle read from a uniform block, with a sample index worked out at run
// time: TLD takes the handle in Rb and the sample index in the register after it.
layout (location = 0) out uvec4 outValue;
layout (std140, binding = 0) uniform Block { uvec2 handle; };

void main()
{
    outValue = texelFetch(usampler2DMS(handle), ivec2(3, 5), int(gl_FragCoord.x) & 3);
}
