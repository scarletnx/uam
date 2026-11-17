#version 460
// dFdy, fwidth and interpolateAtOffset each multiply by STATE_FB_WPOS_Y_TRANSFORM.x, which uam puts in the
// program's own constant buffer.
layout (location = 0) in vec4 inValue;
layout (location = 0) out vec4 outColor;

void main()
{
    outColor = vec4(dFdy(inValue.x), fwidth(inValue.y), interpolateAtOffset(inValue, vec2(0.25, 0.5)).zw);
}
