import glob
import re
import csv
import json
import sys

def uppercase_textsc(s):
    result = s
    textscs = re.findall(r"\\textsc{(.*?)}",s)
    for textsc in textscs:
        result = result.replace(r"\textsc{%s}"%textsc, textsc.upper())
    return result.replace(r'\TEXTSC','').replace(r'\textsc','')


def tex2unicode(s):
    result = s
    result = result.replace("\\textsuperscript{A}","ᴬ")
    result = result.replace("\\textsuperscript{K}","ᴷ")
    result = result.replace("\\stackunder[-10pt]{\\^{i}}{\\'{}}","î́")
    result = result.replace("\\'e","é")
    result = result.replace("\\'u","ú")
    result = result.replace("\\'o","ó")
    result = result.replace("\\'i","í")
    result = result.replace("\\'a","á")
    result = result.replace("{-\\O}","-Ø")
    result = result.replace("{\\O}","Ø")
    return result

def get_imt_blocks(lines, number, textname, glottocode):
    # print(textname)
    blocks = []
    gll_line = None
    examplenumber = 1
    for i,line in enumerate(lines):
        if 'gll' in line:
            # print(line)
            try:
                assert('glt' in lines[i+2])
            except AssertionError:
                # print(lines[i+2].strip())
                if "newpage" in lines[i+2]:
                    assert('glt' in lines[i+3])
                else:
                    print(f"Line {i} does not have \\glt where expected")
                    raise
            orthographic = tex2unicode(lines[i-1].replace('\\textit','').replace('\\\\','').strip())
            morphemic = tex2unicode(lines[i].replace('\\gll','').strip()[:-2])
            gloss = uppercase_textsc(lines[i+1].strip()[:-2].replace('\\_','_'))
            translation = tex2unicode(lines[i+2].replace('\\glt','').strip())
            found_glosses = re.findall("[A-Z][A-Z_]+", gloss)
            abbreviations = {}
            for k in found_glosses:
                try:
                    expansion = abbr[k]
                    abbreviations[k] = expansion
                except KeyError:
                    # pass
                    print(f"no expansion found for abbreviation {k}")
            block = {
               "ID": f'{glottocode}a-{textname}-{examplenumber}',
               "Primary_Text":orthographic,
               "Analyzed_Word": re.sub('  +', ' ', morphemic).replace(' ', '\t').strip(),
               "Gloss": re.sub(r'\s+', ' ', gloss).replace(' ', '\t').strip(),
               "Translated_Text":translation,
               "Text_ID": textname,
               "Sentence_Number": examplenumber,
               "Language_ID": glottocode,
               "OTC_ID": f'{glottocode}a',
               "LGR_Conformance": 'WORD_ALIGNED',
               "Abbreviations": json.dumps(abbreviations)
               }
            lenwords = len(block['Analyzed_Word'].split('\t'))
            lenglosses = len(block['Gloss'].split('\t'))
            try:
                # print(lenwords,lenglosses)
                assert lenwords==lenglosses
            except AssertionError:
                print("number of items do not match")
                print('line', i,":",len(block["Analyzed_Word"].split('\t')),len(block["Gloss"].split('\t')))
                print(block["Analyzed_Word"].split('\t'))
                print(block["Gloss"].split('\t'))
            blocks.append(block)
            examplenumber += 1
    return blocks

if __name__=="__main__":
    found_fieldnames = "ID","Primary_Text","Analyzed_Word","Gloss","Translated_Text","Text_ID","Sentence_Number","Language_ID","OTC_ID","LGR_Conformance","Abbreviations"

    files = sorted(glob.glob("*.tex"))
    print(files)
    global_rows = []
    glottocode = sys.argv[1]
    abbr = json.loads(open("abbr.json").read())
    for j, f in enumerate(files):
        textname = f.split('/')[-1].replace('.tex','').replace('-glossed','')
        print(textname)
        with open(f) as infile:
            lines = infile.readlines()
        global_rows += get_imt_blocks(lines, j+1, textname, glottocode)

    with open("sentences.csv", "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=found_fieldnames)
        writer.writeheader()
        for row in global_rows:
            try:
                del row['LGR']
            except KeyError:
                pass
            try:
                del row['LGRConformance']
            except KeyError:
                pass
            writer.writerow(row)

