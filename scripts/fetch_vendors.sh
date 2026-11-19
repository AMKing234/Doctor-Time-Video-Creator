#!/usr/bin/env bash
# Fetch every optional vendored tool repository.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p vendor

[ -d "vendor/youtube-agent-skill" ] || git clone --depth 1 https://github.com/Jakeschincariol/youtube-agent-skill.git "vendor/youtube-agent-skill"
[ -d "vendor/three.js" ] || git clone --depth 1 https://github.com/mrdoob/three.js.git "vendor/three.js"
[ -d "vendor/pixelfx" ] || git clone --depth 1 https://github.com/patch-gg/pixelfx.git "vendor/pixelfx"
[ -d "vendor/mcp-for-blender" ] || git clone --depth 1 https://github.com/ahujasid/mcp-for-blender.git "vendor/mcp-for-blender"
[ -d "vendor/react-three-rapier" ] || git clone --depth 1 https://github.com/pmndrs/react-three-rapier.git "vendor/react-three-rapier"
[ -d "vendor/react-postprocessing" ] || git clone --depth 1 https://github.com/pmndrs/react-postprocessing.git "vendor/react-postprocessing"
[ -d "vendor/lemo-opuscar" ] || git clone --depth 1 https://github.com/lemomo-ai/lemo-opuscar.git "vendor/lemo-opuscar"
[ -d "vendor/librosa" ] || git clone --depth 1 https://github.com/librosa/librosa.git "vendor/librosa"
[ -d "vendor/video-shotcraft" ] || git clone --depth 1 https://github.com/Vincentwei1021/video-shotcraft.git "vendor/video-shotcraft"
[ -d "vendor/ClaudeAnimationBase" ] || git clone --depth 1 https://github.com/JohnHeibel/ClaudeAnimationBase.git "vendor/ClaudeAnimationBase"
[ -d "vendor/opus-video-prompts" ] || git clone --depth 1 https://github.com/joeseesun/opus-video-prompts.git "vendor/opus-video-prompts"
[ -d "vendor/awesome-opus5-5-videos" ] || git clone --depth 1 https://github.com/yihui-dev/awesome-opus5-5-videos.git "vendor/awesome-opus5-5-videos"
echo "All optional tools present in vendor/."
