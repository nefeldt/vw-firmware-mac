PYTHON ?= python3
.PHONY: check doctor guest native-qemu viewer renderer
check:
	$(PYTHON) scripts/check_release.py
	$(PYTHON) -m compileall -q scripts guest/dsi runtime/graphics tests
	$(PYTHON) -m unittest discover -s tests
doctor:
	$(PYTHON) scripts/doctor.py
guest:
	$(PYTHON) scripts/build_guest.py
native-qemu:
	zsh runtime/qemu-display/build.sh
viewer:
	$(PYTHON) scripts/mib_display_receiver.py
renderer:
	$(PYTHON) runtime/graphics/gl_server.py
