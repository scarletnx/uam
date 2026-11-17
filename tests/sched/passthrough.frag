#version 460
// The last input read sets a write barrier, and the exit after it, in a block of its own, waits on every barrier.
layout (location = 0) flat in vec4 inColor;
layout (location = 0) out vec4 outColor;

void main()
{
    outColor = inColor;
}
