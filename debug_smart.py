import sys, re
sys.path.append('/Volumes/Ark/shell/pyMediaConvert')
from pyMediaTools.core.cjk_tokenizer import CJKTokenizer

text = "Sentence (2 कुरिन्थियों 6:14 देखें)।"
print('text repr',repr(text))
chars=list(text)
starts=[i*0.1 for i in range(len(chars))]
ends=[(i+1)*0.1 for i in range(len(chars))]
words=CJKTokenizer.tokenize_by_cjk(chars,starts,ends)
print('tokens',words)

punctuation_chars=set(__import__('string').punctuation)|set(["।","।","。","，","！","？","、","；","：","“","”","‘","’","（","）","…","—","～","·","《","》","〈","〉"])
parts=[]
for w in words:
    txt=w['text']
    txt=' '.join(txt.split())
    if txt: parts.append(txt)
print('parts',parts)

result=parts[0]
for txt in parts[1:]:
    prev_char=result[-1] if result else ''
    curr_char=txt[0]
    if all(c in punctuation_chars for c in txt):
        result+=txt
    else:
        is_prev_cjk=CJKTokenizer.is_cjk(prev_char)
        is_curr_cjk=CJKTokenizer.is_cjk(curr_char)
        if not is_prev_cjk and not is_curr_cjk and not (curr_char in punctuation_chars):
            result+=' '+txt
        else:
            result+=txt
    print('intermediate',repr(result))

print('before regex',repr(result))
# regex transformations
result=re.sub(r"(?<=[^\s\(])\(", r" (", result)
print('after step1',repr(result))
result=re.sub(r"\( ", "(", result)
print('after step2',repr(result))
result=re.sub(r"(\d)\s*:\s*(\d)", r"\1:\2", result)
print('after colon',repr(result))
result=re.sub(r"\s+\)", ")", result)
print('after close',repr(result))
