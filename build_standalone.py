"""Inline the data so each page is one file you can open by double-clicking."""
import io, os


def bake(page, datafile, outfile):
    html = io.open(page, encoding="utf-8").read()
    data = io.open(datafile, encoding="utf-8").read()

    # Drop the whole fetch(...) statement, whatever its error handling looks like.
    # Matching a literal "});" broke as soon as one page ended with "));", so
    # walk the brackets instead and stop at the semicolon that closes it.
    i = html.index("fetch('" + os.path.basename(datafile) + "')")
    depth, j = 0, i
    while j < len(html):
        ch = html[j]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == ";" and depth == 0:
            j += 1
            break
        j += 1

    # Assign the data where the fetch was, but start AFTER every declaration below
    # it: boot() reads consts that are still in the temporal dead zone up here.
    html = html[:i] + "D = " + data + ";" + html[j:]
    cut = html.rindex("</script>")
    html = html[:cut] + "\nboot();\n" + html[cut:]

    io.open(outfile, "w", encoding="utf-8").write(html)
    print("%s  %.2f MB, no server needed" % (outfile, os.path.getsize(outfile) / 1e6))


bake("out/map.html", "out/map_data.json", "out/pravaah_map.html")
bake("out/dashboard.html", "out/dash_data.json", "out/pravaah_dashboard.html")
bake("out/national.html", "out/national_data.json", "out/pravaah_national.html")
bake("out/citizen.html", "out/patna_citizen_data.json", "out/pravaah_citizen.html")
