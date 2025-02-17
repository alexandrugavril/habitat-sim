// Copyright (c) Facebook, Inc. and its affiliates.
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

#include <Corrade/Containers/Reference.h>
#include <Corrade/Utility/Resource.h>
#include <Magnum/GL/BufferTextureFormat.h>
#include <Magnum/GL/Context.h>
#include <Magnum/GL/Shader.h>
#include <Magnum/GL/Version.h>
#include <Magnum/ImageView.h>
#include <Magnum/PixelFormat.h>

#include "PTexMeshShader.h"
#include "esp/assets/PTexMeshData.h"
#include "esp/core/esp.h"
#include "esp/io/io.h"

// This is to import the "resources" at runtime. // When the resource is
// compiled into static library, it must be explicitly initialized via this
// macro, and should be called // *outside* of any namespace.
static void importShaderResources() {
  CORRADE_RESOURCE_INITIALIZE(ShaderResources)
}

using namespace Magnum;

namespace esp {
namespace gfx {

namespace {
enum TextureBindingPointIndex : uint8_t {
  atlas = 0,
  adjFaces = 1,
};
}

PTexMeshShader::PTexMeshShader() {
  MAGNUM_ASSERT_GL_VERSION_SUPPORTED(GL::Version::GL410);

  if (!Corrade::Utility::Resource::hasGroup("default-shaders")) {
    importShaderResources();
  }

  // this is not the file name, but the group name in the config file
  const Corrade::Utility::Resource rs{"default-shaders"};

  GL::Shader vert{GL::Version::GL410, GL::Shader::Type::Vertex};
  GL::Shader geom{GL::Version::GL410, GL::Shader::Type::Geometry};
  GL::Shader frag{GL::Version::GL410, GL::Shader::Type::Fragment};

  vert.addSource(rs.get("ptex-default-gl410.vert"));
  geom.addSource(rs.get("ptex-default-gl410.geom"));
  frag.addSource(rs.get("ptex-default-gl410.frag"));

  CORRADE_INTERNAL_ASSERT_OUTPUT(GL::Shader::compile({vert, geom, frag}));

  attachShaders({vert, geom, frag});

  CORRADE_INTERNAL_ASSERT_OUTPUT(link());

  // set texture binding points in the shader;
  // see ptex fragment shader code for details
  setUniform(uniformLocation("atlasTex"), TextureBindingPointIndex::atlas);
  // TODO: disable the "meshAdjFaces" on Mac
  setUniform(uniformLocation("meshAdjFaces"),
             TextureBindingPointIndex::adjFaces);

  // cache the uniform locations
  MVPMatrixUniform_ = uniformLocation("MVP");
  exposureUniform_ = uniformLocation("exposure");
  gammaUniform_ = uniformLocation("gamma");
  saturationUniform_ = uniformLocation("saturation");
  tileSizeUniform_ = uniformLocation("tileSize");
  widthInTilesUniform_ = uniformLocation("widthInTiles");
}

// Note: the texture binding points are explicitly specified above.
// Cannot use "explicit uniform location" directly in shader since
// it requires GL4.3 (We stick to GL4.1 for MacOS).
PTexMeshShader& PTexMeshShader::bindAtlasTexture(
    Magnum::GL::Texture2D& texture) {
  texture.bind(TextureBindingPointIndex::atlas);
  return *this;
}

PTexMeshShader& PTexMeshShader::bindAdjFacesBufferTexture(
    Magnum::GL::BufferTexture& texture) {
  texture.bind(TextureBindingPointIndex::adjFaces);
  return *this;
}

PTexMeshShader& PTexMeshShader::setMVPMatrix(const Magnum::Matrix4& matrix) {
  setUniform(MVPMatrixUniform_, matrix);
  return *this;
}

PTexMeshShader& PTexMeshShader::setExposure(float exposure) {
  setUniform(exposureUniform_, exposure);
  return *this;
}
PTexMeshShader& PTexMeshShader::setGamma(float gamma) {
  setUniform(gammaUniform_, gamma);
  return *this;
}

PTexMeshShader& PTexMeshShader::setSaturation(float saturation) {
  setUniform(saturationUniform_, saturation);
  return *this;
}

PTexMeshShader& PTexMeshShader::setAtlasTextureSize(
    Magnum::GL::Texture2D& texture,
    uint32_t tileSize) {
  setUniform(tileSizeUniform_, (int)tileSize);

  // get image width in given mip level 0
  int mipLevel = 0;
  const auto width = texture.imageSize(mipLevel).x();
  setUniform(widthInTilesUniform_, int(width / tileSize));
  return *this;
}

}  // namespace gfx
}  // namespace esp
