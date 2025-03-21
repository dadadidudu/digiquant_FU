import re
import os
from ..files import Files

def as_html(title, body):
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta http-equiv=Content-Type content="text/html">
<title>{title}</title>
</head>
<body>
{body}
</body>
</html>
"""


class ExtractPublications:
    """
    This class extracts the text of a given HTML file ("publication") and writes it to its own file.
    """

    @staticmethod
    def extract_text(input_file: str, output_path: str,
                    ignore: list[int] = [], delete_existing=False, html_tag: str = "div"
                    ) -> list[str]:
        '''
        Extracts the body (i.e. everything that is found as a child of the optionally supplied html_tag)
        of the given publication HTML input file (path, name, ext) to the given output path.
        Optionally ignores the publications at the given ignore indices,
        and optionally deletes the existing output path (and all of its contents), if it exists.
        '''

        body: str = ""

        if delete_existing:
            Files.delete_folder(output_path)

        # read html file and extract body
        with open(input_file) as file:
            content = file.read()
            body = ExtractPublications.get_text_between_tags(html_tag, content)

        # find all h1 and write them as seperate html files
        startpos = -1
        endpos = -1
        num_h1 = sum(1 for _ in re.finditer("<h1", body))
        curr_match = 1
        for match in re.finditer("<h1", body):
            startpos = endpos
            endpos = match.span()[0]
            if startpos == -1:
                # first: skip (no endpos)
                continue
            else:
                content = body[startpos:endpos-1]
                # surround with html tags
                Files.write_file(
                    output_path, f"{curr_match}.html", as_html(f"publication {curr_match}", content))

            if curr_match + 1 == num_h1:
                # last:
                content = body[endpos:]
                Files.write_file(
                    output_path, f"{curr_match + 1}.html", as_html(f"publication {curr_match}", content))

            curr_match += 1

        for ignorefile_idx in ignore:
            os.unlink(os.path.join(output_path, f"{ignorefile_idx}.html"))

        extracted_files: list[str] = []
        for f in os.listdir(output_path):
            if os.path.isfile(os.path.join(output_path, f)):
                extracted_files.append(os.path.join(output_path, f))
        return extracted_files


    @staticmethod
    def get_text_between_tags(tag: str, content: str) -> str:
        "Returns the text content between the opening and the closing of a HTML tag."
        
        start = content.find(f"<{tag}")
        end = content.rfind(f"</{tag}>") + len(f"</{tag}>")
        text = content[start:end]
        return text
