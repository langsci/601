#!/usr/bin/env python3

import argparse
import io
import os
import sys
import fitz
from PIL import Image


def make_jpeg(pix, width, height, quality):
    if pix.alpha or pix.colorspace is None:
        return None

    if pix.n not in (1, 3):
        pix = fitz.Pixmap(fitz.csRGB, pix)

    mode = "L" if pix.n == 1 else "RGB"
    img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)

    if width < img.width or height < img.height:
        img = img.resize(
            (width, height),
            Image.Resampling.LANCZOS
        )

    out = io.BytesIO()
    img.save(
        out,
        "JPEG",
        quality=quality,
        optimize=True,
        progressive=False
    )
    return out.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--quality", type=int, default=72)
    parser.add_argument("--min-kb", type=int, default=50)
    args = parser.parse_args()

    if args.input == args.output:
        sys.exit("Input and output must be different files.")

    doc = fitz.open(args.input)
    metadata = dict(doc.metadata)

    #
    # Determine the largest displayed size of every image.
    #
    # PDF coordinates are points: 72 points = 1 inch.
    #
    usage = {}

    print("Scanning image placement...")

    for page in doc:
        for img in page.get_images(full=True):
            xref = img[0]

            try:
                rects = page.get_image_rects(xref)
            except Exception:
                continue

            for rect in rects:
                w_pt = abs(rect.width)
                h_pt = abs(rect.height)

                if w_pt <= 0 or h_pt <= 0:
                    continue

                if xref not in usage:
                    usage[xref] = [w_pt, h_pt]
                else:
                    usage[xref][0] = max(usage[xref][0], w_pt)
                    usage[xref][1] = max(usage[xref][1], h_pt)

    print(f"Found {len(usage)} placed image objects.")

    replaced = 0
    skipped = 0

    for number, (xref, dimensions) in enumerate(usage.items(), 1):

        try:
            info = doc.extract_image(xref)

            if not info:
                skipped += 1
                continue

            original = info["image"]
            width = info["width"]
            height = info["height"]
            ext = info.get("ext", "?")

            old_size = len(original)

            if old_size < args.min_kb * 1024:
                skipped += 1
                continue

            if info.get("smask", 0):
                print(f"xref {xref}: skip mask/transparency")
                skipped += 1
                continue

            display_w_pt, display_h_pt = dimensions

            #
            # Required pixel dimensions at target DPI.
            #
            target_w = round(display_w_pt / 72 * args.dpi)
            target_h = round(display_h_pt / 72 * args.dpi)

            #
            # Never upscale.
            #
            scale = min(
                1.0,
                target_w / width,
                target_h / height
            )

            new_w = max(1, round(width * scale))
            new_h = max(1, round(height * scale))

            effective_dpi_x = width / (display_w_pt / 72)
            effective_dpi_y = height / (display_h_pt / 72)

            pix = fitz.Pixmap(doc, xref)

            new_data = make_jpeg(
                pix,
                new_w,
                new_h,
                args.quality
            )

            if not new_data:
                skipped += 1
                continue

            if len(new_data) >= old_size:
                print(
                    f"[{number}/{len(usage)}] xref {xref}: keep "
                    f"{width}x{height}, "
                    f"{old_size/1024:.0f} KB"
                )
                skipped += 1
                continue

            #
            # Find a page containing this image and replace its
            # underlying XObject.
            #
            replacement_page = None

            for page in doc:
                if any(i[0] == xref for i in page.get_images(full=True)):
                    replacement_page = page
                    break

            if replacement_page is None:
                skipped += 1
                continue

            replacement_page.replace_image(
                xref,
                stream=new_data
            )

            replaced += 1

            print(
                f"[{number}/{len(usage)}] xref {xref}: "
                f"{width}x{height} -> {new_w}x{new_h}  "
                f"DPI {effective_dpi_x:.0f}x{effective_dpi_y:.0f}  "
                f"{old_size/1024:.0f} KB -> "
                f"{len(new_data)/1024:.0f} KB"
            )

        except Exception as e:
            print(f"xref {xref}: skipped ({e})")
            skipped += 1

    doc.set_metadata(metadata)

    print("Saving PDF...")

    doc.save(
        args.output,
        garbage=4,
        deflate=True,
        clean=False,
        pretty=False
    )

    doc.close()

    old_pdf = os.path.getsize(args.input)
    new_pdf = os.path.getsize(args.output)

    print()
    print(f"Images replaced : {replaced}")
    print(f"Images skipped  : {skipped}")
    print(f"Original PDF    : {old_pdf/1024/1024:.1f} MB")
    print(f"Output PDF      : {new_pdf/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
