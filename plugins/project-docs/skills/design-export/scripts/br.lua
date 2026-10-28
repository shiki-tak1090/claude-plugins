-- 表のセル内の <br> を Word の改行に変える（pandoc は docx 出力時に HTML タグを捨てるため）
function RawInline(el)
  if el.format:match("html") and el.text:match("^<br%s*/?>$") then
    return pandoc.LineBreak()
  end
end
