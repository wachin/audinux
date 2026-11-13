PREFIX ?= /usr

.PHONY: install uninstall

install:
	python3 -m pip install . --prefix=$(PREFIX) --upgrade --no-deps
	install -Dm644 packaging/audinux.desktop $(DESTDIR)$(PREFIX)/share/applications/audinux.desktop
	install -Dm644 packaging/audinux.svg $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/audinux.svg
	install -d $(DESTDIR)$(PREFIX)/share/audinux/i18n
	# If you have compiled qm files, copy them here:
	# install -Dm644 packaging/i18n/*.qm $(DESTDIR)$(PREFIX)/share/audinux/i18n/ || true

uninstall:
	python3 -m pip uninstall -y audinux || true
	rm -f $(DESTDIR)$(PREFIX)/share/applications/audinux.desktop
	rm -f $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/audinux.svg
	rm -rf $(DESTDIR)$(PREFIX)/share/audinux
