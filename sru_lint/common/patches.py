def make_start_filename_matcher(pattern: str):
    def match_filename(filename: str):
        return filename.startswith(pattern)
    return match_filename

def make_end_filename_matcher(pattern: str):
    def match_filename(filename: str):
        return filename.endswith(pattern)
    return match_filename

def make_contains_filename_matcher(pattern: str):
    def match_filename(filename: str):
        return pattern in filename
    return match_filename

def match_hunks(patches, filename_predicate):
    output = {}
    for patch in patches:
        print(f"Checking patch: {patch.source_file}")
        if filename_predicate(patch.source_file):
            content = ''.join(
                line.value
                for hunk in patch
                for line in hunk
                if line.is_added
            )
            output[patch.source_file] = content
    return output

def combine_added_lines(patched_file, include_context=False):
    content = ''.join(
        line.value
        for hunk in patched_file
        for line in hunk
        if line.is_added or (include_context and line.is_context)
    )
    return {patched_file.path: content}