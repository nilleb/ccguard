from colour import Color


simple_image_format = """<svg xmlns="http://www.w3.org/2000/svg" width="112" height="20">
    <linearGradient id="b" x2="0" y2="100%">
        <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
        <stop offset="1" stop-opacity=".1"/>
    </linearGradient>
    <mask id="a">
        <rect width="96" height="20" rx="3" fill="#fff"/>
    </mask>
    <g mask="url(#a)">
        <path fill="#555" d="M0 0h60v20H0z"/>
        <path fill="{color}" d="M60 0h36v20H60z"/>
        <path fill="url(#b)" d="M0 0h96v20H0z"/>
    </g>
    <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
        <text x="30" y="15" fill="#010101" fill-opacity=".3">coverage</text>
        <text x="30" y="14">coverage</text>
        <text x="80" y="15" fill="#010101" fill-opacity=".3">{pct}</text>
        <text x="80" y="14">{pct}</text>
    </g>
</svg>
"""

width = 5
number_of_items = 101
red = Color("red")
green = Color("green")
colors = list(red.range_to(green, number_of_items))

with open("test_image.svg", "w") as test_image:
    test_image.write(
        '<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="20">\n'.format(
            width * number_of_items
        )
    )

    for idx, color in enumerate(colors):
        begin = idx * width
        end = (idx + 1) * width
        current = '<path fill="{color}" d="M{begin} 0h{end}v20H{begin}z"/>\n'.format(
            color=color, begin=begin, end=end
        )
        test_image.write(current)

    test_image.write("</svg>")

with open("test_page.html", "w") as test_page:
    test_page.write("<html><head></head><body>")

    for idx, color in enumerate(colors):
        current = simple_image_format.format(color=color, pct=idx)
        test_page.write(current)

    test_page.write("</body></html>")
