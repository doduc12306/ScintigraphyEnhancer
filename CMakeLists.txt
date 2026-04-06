cmake_minimum_required(VERSION 3.20.6...3.22.6 FATAL_ERROR)

project(ScintigraphyEnhancer)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://www.slicer.org/wiki/Documentation/Nightly/Extensions/ScintigraphyEnhancer")
set(EXTENSION_CONTRIBUTORS "Duc Do")
set(EXTENSION_DESCRIPTION "ScintigraphyEnhancer: Preprocessing toolkit for PET/SPECT in 3D Slicer")
set(EXTENSION_ICONURL "")
set(EXTENSION_SCREENSHOTURLS "")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(ScintigraphyEnhancer)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
