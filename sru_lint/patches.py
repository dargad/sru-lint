
def make_filename_matcher(pattern: str):
    def match_filename(filename: str):
        return filename.endswith(pattern)
    return match_filename

def match_hunks(patches, filename_predicate):
    output = {}
    for patch in patches:
        if filename_predicate(patch.source_file):
            content = ''.join(
                line.value
                for hunk in patch
                for line in hunk
                if line.is_added
            )
            output[patch.source_file] = content
    return output