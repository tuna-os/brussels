kind: manual
description: |
  Chicago95 GTK, xfwm4 and notification themes, icon theme, cursor themes
  and xfce4-terminal colour scheme, built from the upstream source tree
  (github.com/grassmunk/Chicago95, GPL-3.0+/MIT). Used by the
  brussels-winblues variant only; see docs/winblues.md.

  Not installed, on purpose: the sound theme and the startup sound (their
  provenance is Windows 95 audio), the Chicago95 Plymouth theme (a replica
  of the Windows 95 boot screen), the wallpapers, the fonts, and the
  theme's start-button images. Icons that draw the Windows flag, the
  Internet Explorer "e" or the Office document marks are removed, and the
  menu/start-here names get the theme's own Tux icon instead. The build
  fails if a removed image survives under another file name.

  The last tag (v3.0.1) is from June 2022 and lacks 164 later fixes, so
  this pins a master commit (docs/winblues.md).

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-make.bst
# gtk-update-icon-cache
- freedesktop-sdk.bst:components/gtk3.bst

sources:
- kind: git_repo
  url: github:grassmunk/Chicago95.git
  track: master
  ref: v3.0.1-164-g5da19b8b1e2a886ebf6628403023d5fac3acc3ee

variables:
  strip-binaries: ""

config:
  install-commands:
  - |
    set -eu
    themes="%{install-root}%{datadir}/themes"
    icons="%{install-root}%{datadir}/icons"
    mkdir -p "$themes" "$icons" "%{install-root}%{datadir}/xfce4/terminal/colorschemes"

    # GTK 2/3/4, xfwm4 (read by xfwl4) and xfce4-notifyd themes. The other
    # desktops' themes and misc/ (start-button and Windows logo images) stay out.
    cp -a Theme/Chicago95 "$themes/"
    for d in gnome-shell cinnamon metacity-1 openbox-3 misc; do
      rm -rf "$themes/Chicago95/$d"
    done
    # The Windows word mark, and the flag and "e" badges and busy animation.
    rm -rf "$themes"/Chicago95/gtk-3.0/assets/branding_W95*.png \
           "$themes"/Chicago95/gtk-3.0/assets/status_badge_ie.png \
           "$themes"/Chicago95/gtk-3.0/assets/status_badge_msw.png \
           "$themes"/Chicago95/gtk-3.0/assets/throbber

    cp -a Icons/Chicago95 "$icons/"
    cp -a Cursors/Chicago95_Animated_Hourglass_Cursors Cursors/Chicago95_Standard_Cursors "$icons/"
    install -m 0644 Extras/Chicago95.theme \
      "%{install-root}%{datadir}/xfce4/terminal/colorschemes/Chicago95.theme"

    # The GPL text and the notice are in files/winblues (winblues/config.bst).
    install -D -m 0644 CREDITS "%{install-root}%{datadir}/licenses/chicago95/CREDITS"

    # Trademarked artwork: the Windows flag (start/menu/distributor icons),
    # the Internet Explorer "e" (Chromium/Chrome icons), the MSN, MS-DOS and
    # Visual Studio logos, and the Office marks (also under LibreOffice and
    # OpenDocument names). The names below seed a list of image hashes; every
    # icon with one of those hashes goes, whatever its name, and so does
    # every symlink left dangling.
    blocked="$(mktemp)"
    cd "$icons/Chicago95"
    set -- \( -name 'start-here*' -o -name 'xfdesktop-menu*' -o -name 'distributor-logo*' \
              -o -name 'chromium-browser*' -o -name 'google-chrome*' \
              -o -name 'application-msword*' -o -name 'application-vnd.ms-*' \
              -o -name 'application-vnd.openxmlformats-*' -o -name 'xfce4-panel-menu*' \
              -o -name 'xfce4-whiskermenu*' -o -name 'xfce4-logo*' -o -name 'wine.*' \
              -o -name 'software-update-available*' -o -name 'software-update-urgent*' \
              -o -name 'application-x-ms-dos-executable*' -o -name 'application-x-ms-shortcut*' \
              -o -name 'application-x-sln*' -o -name 'com.visualstudio*' -o -name 'im-msn*' \
              -o -name 'folder-download*' -o -name 'folder_download*' -o -name 'msaccess*' \
              -o -name 'libreoffice-base*' -o -name 'libreoffice-calc*' -o -name 'libreoffice-draw.*' \
              -o -name 'libreoffice-impress*' -o -name 'libreoffice-main*' -o -name 'libreoffice-math*' \
              -o -name 'libreoffice-writer*' -o -name 'libreoffice-text*' \
              -o -name 'libreoffice-presentation*' -o -name 'libreoffice-spreadsheet*' \
              -o -name 'ooo-*' -o -name 'x-office-presentation*' -o -name 'x-office-spreadsheet*' \
              -o -name 'application-vnd.oasis.opendocument.chart*' \)
    find . "$@" -type f -exec md5sum {} + | cut -d' ' -f1 | sort -u > "$blocked"
    find . -type f -exec md5sum {} + | grep -F -f "$blocked" | cut -d' ' -f3- \
      | while IFS= read -r f; do rm -f "$f"; done
    find . "$@" -exec rm -f {} +
    find . -xtype l -delete

    # The download folder had the "e"; it gets the plain folder instead.
    for dir in places/*; do
      for ext in png svg; do
        [ -e "$dir/folder.$ext" ] || continue
        for name in folder-download folder-downloads; do
          ln -s "folder.$ext" "$dir/$name.$ext"
        done
      done
    done

    # Start-menu icon: the Tux from the theme's own Chicago95-tux variant
    # (Tux by Larry Ewing, made with The GIMP), at every size it has.
    tux="%{build-root}/Icons/Chicago95-tux/places"
    for dir in "$tux"/*; do
      size="$(basename "$dir")"
      for img in "$dir"/start-here.png "$dir"/start-here.svg; do
        [ -f "$img" ] && [ ! -L "$img" ] || continue
        ext="${img##*.}"
        for cat in places categories apps; do
          [ -d "$cat/$size" ] || continue
          for name in start-here xfdesktop-menu xfce4-panel-menu distributor-logo; do
            install -m 0644 "$img" "$cat/$size/$name.$ext"
          done
        done
      done
    done

    # Audit: no removed image may survive under another name, anywhere in
    # what this element installs.
    sort -u -o "$blocked" "$blocked"
    found="$(cd "%{install-root}" && find . -type f -exec md5sum {} + | grep -F -f "$blocked" || true)"
    if [ -n "$found" ]; then
      echo "trademarked artwork still installed:" >&2
      echo "$found" >&2
      exit 1
    fi
    rm -f "$blocked"

    cd "%{install-root}"
    rm -f "$icons/Chicago95/icon-theme.cache"
    gtk-update-icon-cache -f -t "$icons/Chicago95"
