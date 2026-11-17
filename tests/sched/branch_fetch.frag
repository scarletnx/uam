#version 460
// A texture read that ends one block, read in the next one.
layout (location = 0) in vec2 inUv;
layout (location = 0) out vec4 outColor;
layout (binding = 0) uniform sampler2D tex;
layout (std140, binding = 0) uniform Params { vec4 scale; };

void main()
{
    vec4 c = scale;
    if (inUv.x > 0.5)
        c = texture(tex, inUv);
    outColor = c * scale.y;
}
