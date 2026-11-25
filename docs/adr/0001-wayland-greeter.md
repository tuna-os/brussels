# ADR 0001: Display manager / greeter for XFCE Wayland

Status: proposed · 2026-07-19

## Context

Brussels runs XFCE on Wayland through the xfwl4 compositor. The traditional
stack for XFCE login uses LightDM and lightdm-gtk-greeter, which support only
X11. LightDM can *start* Wayland sessions, but the GTK greeter renders through
X. This adds Xorg to an image that otherwise uses only Wayland.

Today, the image inherits **GDM** from the gnomeos base. The live ISO uses GDM
for automatic login. This works, but it adds GNOME Shell components to a
"vanilla XFCE" system. The login screen also looks like GNOME.

## Options

1. **Keep GDM and add brand assets.** This option needs no development work,
   but has the largest footprint. It uses gnome-shell as the greeter and the
   lock screen behavior from GNOME. It is acceptable as a temporary option.
2. **Use greetd with gtkgreet or regreet under xfwl4 or cage.** Greetd is a
   small manager for sessions. Regreet (GTK4) and gtkgreet can run under any
   Wayland compositor. They can use cage, or xfwl4 when it is stable. This
   option is small, native to Wayland, and themeable with XFCE assets. Most
   wlroots distributions use it. Effort: package definitions, a session config
   element, and PAM config. Upstream XFCE has not formally approved it, but it
   is compatible with XFCE.
3. **Port lightdm-gtk-greeter to Wayland.** This provides an official greeter
   on Wayland. It needs Wayland seat support in LightDM and a rewrite of the
   greeter for GTK4 and layer shell. This option has the largest effort and
   needs coordination with the xfce and LightDM maintainers. It would be a
   direct upstream contribution and support the goal for an official XFCE
greeter.

## Decision (proposed)

Short term: keep GDM (option 1) — it works and the live ISO depends on its
autologin today.
Target: **option 2 (greetd + regreet)** as the shipped greeter for the
opinionated XFCE layer, branded with Brussels assets.
Long term / upstream track: prototype option 3 with the XFCE project if it has
interest. This could become the official greeter for XFCE on Wayland.

## Consequences

- A `greetd` element + `regreet` element + session-config change, and the
  live ISO's autologin has to move from GDM custom.conf to greetd's
  `initial_session`.
- The image can then exclude GNOME Shell and GDM, which decreases its size.
- Revisit the decision when xfwl4 can host the greeter in kiosk mode. At that
  point, the image can remove the cage dependency.
