--standalone --macos-app-icon=Icon.icns \                  
       --macos-create-app-bundle \
       --output-dir=dist-nuitka \
       --plugin-enable=pyside6 \
       --include-package=pyMediaConvert \
       --include-data-dir=bin=bin \
       --include-data-dir=assets=assets \
       MediaTools.py