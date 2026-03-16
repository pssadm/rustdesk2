#!/usr/bin/env python3
"""
apply-branding.py — Patches a RustDesk source tree with custom branding.

Reads a JSON config file and applies:
  1. App name, server, and public key to libs/hbb_common/src/config.rs
  2. Package metadata to Cargo.toml
  3. Icon/logo assets to platform-specific locations
  4. App name replacements in language files
  5. Linux .desktop file updates

Usage:
  python3 apply-branding.py --config custom-config.json --assets assets/icons/

Must be run from the root of a RustDesk source checkout.
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys


def load_config(path):
    if not os.path.isfile(path):
        print(f"ERROR: Config file not found: {path}")
        sys.exit(1)
    with open(path, "r") as f:
        return json.load(f)


def patch_config_rs(config):
    """Patch libs/hbb_common/src/config.rs with app name, servers, and key."""
    filepath = os.path.join("libs", "hbb_common", "src", "config.rs")
    if not os.path.isfile(filepath):
        print(f"  WARNING: {filepath} not found, skipping config.rs patching")
        return False

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    original = content

    # Patch APP_NAME — it's a RwLock<String> in lazy_static, not a const
    app_name = config["app_name"]
    content = re.sub(
        r'(pub\s+static\s+ref\s+APP_NAME\s*:\s*RwLock<String>\s*=\s*RwLock::new\()"[^"]*"(\.to_owned\(\)\s*\)\s*;)',
        f'\\1"{app_name}"\\2',
        content,
    )
    # Fallback: also try const pattern in case upstream changes it
    content = re.sub(
        r'(pub\s+)?const\s+APP_NAME\s*:\s*&\s*str\s*=\s*"[^"]*"\s*;',
        f'pub const APP_NAME: &str = "{app_name}";',
        content,
    )

    # Patch RENDEZVOUS_SERVERS
    servers = config.get("rendezvous_servers", [])
    servers_str = ", ".join(f'"{s}"' for s in servers)
    content = re.sub(
        r'(pub\s+)?const\s+RENDEZVOUS_SERVERS\s*:\s*&\[&str\]\s*=\s*&\[[^\]]*\]\s*;',
        f"pub const RENDEZVOUS_SERVERS: &[&str] = &[{servers_str}];",
        content,
    )

    # Patch RS_PUB_KEY
    pub_key = config.get("public_key", "")
    content = re.sub(
        r'(pub\s+)?const\s+RS_PUB_KEY\s*:\s*&\s*str\s*=\s*"[^"]*"\s*;',
        f'pub const RS_PUB_KEY: &str = "{pub_key}";',
        content,
    )

    # Patch API_SERVER if present
    api_server = config.get("api_server", "")
    if api_server:
        content = re.sub(
            r'(pub\s+)?const\s+API_SERVER\s*:\s*&\s*str\s*=\s*"[^"]*"\s*;',
            f'pub const API_SERVER: &str = "{api_server}";',
            content,
        )

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  Patched {filepath}")
        return True
    else:
        print(f"  WARNING: No changes made to {filepath} — regex patterns may not match")
        return False


def patch_cargo_toml(config):
    """Patch Cargo.toml with package metadata."""
    filepath = "Cargo.toml"
    if not os.path.isfile(filepath):
        print(f"  WARNING: {filepath} not found, skipping")
        return False

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    original = content
    app_name = config["app_name"]
    slug = re.sub(r"[^a-z0-9]+", "-", app_name.lower()).strip("-")
    description = config.get("description", app_name)
    author = config.get("author", "")
    identifier = config.get("app_identifier", f"com.example.{slug}")

    # NOTE: Do NOT change the crate name or default-run fields.
    # The crate name must remain "rustdesk" because flutter_rust_bridge
    # code generation depends on it. Only change display metadata.

    # Update description
    content = re.sub(
        r'(^\s*description\s*=\s*)"[^"]*"',
        f'\\1"{description}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )

    # Update bundle name in [package.metadata.bundle] section
    content = re.sub(
        r'(\[package\.metadata\.bundle\][^\[]*?name\s*=\s*)"[^"]*"',
        f'\\1"{app_name}"',
        content,
        flags=re.DOTALL,
    )

    # Update bundle identifier
    content = re.sub(
        r'(\[package\.metadata\.bundle\][^\[]*?identifier\s*=\s*)"[^"]*"',
        f'\\1"{identifier}"',
        content,
        flags=re.DOTALL,
    )

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  Patched {filepath}")
        return True
    else:
        print(f"  WARNING: No changes made to {filepath}")
        return False


def copy_icons(assets_dir):
    """Copy icon assets to their platform-specific locations."""
    copies = [
        ("icon-windows.ico", os.path.join("flutter", "windows", "runner", "resources", "app_icon.ico")),
        ("logo.svg", os.path.join("flutter", "assets", "logo.svg")),
        ("icon-512.png", os.path.join("res", "512x512.png")),
        ("icon-128.png", os.path.join("res", "128x128.png")),
        ("icon-128.png", os.path.join("res", "128x128@2x.png")),
        ("icon-32.png", os.path.join("res", "32x32.png")),
    ]

    any_copied = False
    for src_name, dest_path in copies:
        src = os.path.join(assets_dir, src_name)
        if os.path.isfile(src):
            dest_dir = os.path.dirname(dest_path)
            if dest_dir and not os.path.isdir(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
            shutil.copy2(src, dest_path)
            print(f"  Copied {src_name} -> {dest_path}")
            any_copied = True
        else:
            print(f"  WARNING: {src} not found, skipping")

    # macOS iconset generation from icon-1024.png
    icon_1024 = os.path.join(assets_dir, "icon-1024.png")
    macos_iconset_dir = os.path.join(
        "flutter", "macos", "Runner", "Assets.xcassets", "AppIcon.appiconset"
    )
    if os.path.isfile(icon_1024):
        if os.path.isdir(macos_iconset_dir):
            # Generate multiple sizes for macOS using available tools
            macos_sizes = [16, 32, 64, 128, 256, 512, 1024]
            converter = None
            if shutil.which("sips"):
                converter = "sips"
            elif shutil.which("convert"):
                converter = "imagemagick"

            if converter:
                for size in macos_sizes:
                    out_file = os.path.join(macos_iconset_dir, f"app_icon_{size}.png")
                    try:
                        if converter == "sips":
                            subprocess.run(
                                ["sips", "-z", str(size), str(size), icon_1024, "--out", out_file],
                                check=True, capture_output=True,
                            )
                        else:
                            subprocess.run(
                                ["convert", icon_1024, "-resize", f"{size}x{size}", out_file],
                                check=True, capture_output=True,
                            )
                        print(f"  Generated macOS icon {size}x{size}")
                    except (subprocess.CalledProcessError, FileNotFoundError) as e:
                        print(f"  WARNING: Failed to generate {size}x{size} macOS icon: {e}")
                any_copied = True
            else:
                # Fallback: just copy the 1024 as-is
                shutil.copy2(icon_1024, os.path.join(macos_iconset_dir, "app_icon_1024.png"))
                print(f"  Copied icon-1024.png to macOS iconset (no sips/imagemagick for resizing)")
                any_copied = True
        else:
            print(f"  WARNING: macOS iconset directory not found at {macos_iconset_dir}")
    else:
        print(f"  WARNING: {icon_1024} not found, skipping macOS icons")

    return any_copied


def patch_lang_files(config):
    """Replace 'RustDesk' with custom app name in language string files and Flutter Dart files."""
    app_name = config["app_name"]

    # Collect both Rust lang files AND Flutter Dart files
    lang_files = glob.glob(os.path.join("src", "lang", "*.rs"))
    lang_files += glob.glob(os.path.join("flutter", "lib", "**", "*.dart"), recursive=True)

    if not lang_files:
        print("  WARNING: No language files found")
        return False

    count = 0
    for filepath in lang_files:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Replace "RustDesk" in string literals only (between quotes)
        new_content = re.sub(r'("(?:[^"\\]|\\.)*")', lambda m: m.group(0).replace("RustDesk", app_name), content)

        if new_content != content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            count += 1

    if count:
        print(f"  Patched {count} language file(s) with app name '{app_name}'")
    else:
        print("  No 'RustDesk' references found in language files")
    return count > 0


def patch_desktop_files(config):
    """Update Name= in .desktop files under flutter/."""
    app_name = config["app_name"]
    desktop_files = glob.glob(os.path.join("flutter", "**", "*.desktop"), recursive=True)

    if not desktop_files:
        print("  WARNING: No .desktop files found under flutter/")
        return False

    count = 0
    for filepath in desktop_files:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        new_content = re.sub(
            r"^(Name\s*=\s*).*$",
            f"\\g<1>{app_name}",
            content,
            flags=re.MULTILINE,
        )

        if new_content != content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"  Patched {filepath}")
            count += 1

    return count > 0


def main():
    parser = argparse.ArgumentParser(description="Apply custom branding to RustDesk source tree")
    parser.add_argument("--config", default="custom-config.json", help="Path to branding config JSON")
    parser.add_argument("--assets", default=os.path.join("assets", "icons"), help="Path to icon assets directory")
    args = parser.parse_args()

    print(f"Loading config from: {args.config}")
    config = load_config(args.config)
    print(f"  App name: {config['app_name']}")
    print(f"  Servers: {config.get('rendezvous_servers', [])}")
    print()

    print("[1/5] Patching config.rs...")
    patch_config_rs(config)
    print()

    print("[2/5] Patching Cargo.toml...")
    patch_cargo_toml(config)
    print()

    print("[3/5] Copying icon assets...")
    copy_icons(args.assets)
    print()

    print("[4/5] Patching language files...")
    patch_lang_files(config)
    print()

    print("[5/5] Patching .desktop files...")
    patch_desktop_files(config)
    print()

    print("Branding applied successfully.")


if __name__ == "__main__":
    main()
