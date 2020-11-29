from bottle import default_app, route, run, template, static_file, error, request
import docx2txt
import fitz #PyMuPDF
import re
import os
import sqlite3

save_path="./save_file"
if not os.path.exists(save_path):
    os.mkdir(save_path)

from natasha import (
    Segmenter,
    MorphVocab,

    NewsEmbedding,
    NewsMorphTagger,
    NewsSyntaxParser,
    NewsNERTagger,

    Doc
)

segmenter = Segmenter()
morph_vocab = MorphVocab()

emb = NewsEmbedding()
morph_tagger = NewsMorphTagger(emb)
syntax_parser = NewsSyntaxParser(emb)
ner_tagger = NewsNERTagger(emb)

ext_docs = ['docx']#, 'pdf'

conn = sqlite3.connect('./resume.db')

title_page_add = 'Ввод файлов резюме в БД'
title_edit = 'Корректировка'
title_key_words = 'Конструктор вакансий'#'Ключевые слова по специальностям'

@error(405)
@error(404)
@error(403)
def mistake(code):
    return index()

@route('/')
def index():
    return template('index', title = 'Цифровой ассистент сотрудника по подбору персонала',
                    page = '', messege = [])

@route('/edit', method='GET')
def edit_get():
    cursor = conn.cursor()
    cursor.execute("SELECT id, substr(text, 0, 250)||' ...' as text, file_load, fio, email, telefon, \
                   comment_ok, comment_ruk, tests, deleted FROM files order by id desc")
    result = cursor.fetchall()
    cursor.close()
    return template('index', title = title_edit, page = 'edit', messege = result)

@route('/edit', method='POST')
def edit_post():
    correct = request.forms.get('correct', '').strip()
    input_hidden = request.forms.get('input_hidden', '').strip()
    if input_hidden and correct:
        correct = str(request.forms.decode()['correct'])
        input_hidden = str(request.forms.decode()['input_hidden'])

        input_hidden = input_hidden.split('_')
        rows = ['id', 'text', 'file_load', 'fio', 'email', 'telefon', 'comment_ok', 'comment_ruk',
                'tests', 'deleted']
        int_row = int(input_hidden[1])
        if int_row > 2:
            cursor = conn.cursor()
            cursor.execute("UPDATE files SET " +rows[int_row]+ " = ? WHERE id = ?",
                           (correct, input_hidden[0]))
            conn.commit()
            cursor.close()

    return edit_get()

@route('/search', method='GET')
def search():
    final_result = []
    search = request.GET.get('search', '').strip()
    search_lemma = request.GET.get('search_lemma', '').strip()
    search_strong = request.GET.get('search_strong', '').strip()
    if search:
        search = str(request.query.decode()['search'])
        if search_lemma == 'checked':
            doc = Doc(search)
            doc.segment(segmenter)
            doc.tag_morph(morph_tagger)
            doc.parse_syntax(syntax_parser)
            doc.tag_ner(ner_tagger)
            for token in doc.tokens:
                token.lemmatize(morph_vocab)
            search_lower = ' '.join([_.lemma for _ in doc.tokens])
        else:
            search_lower = search.lower()
            search_lower = re.sub(r"  ", " ", search_lower)

        if search_strong == 'checked':
            text_like = 'text_lemma LIKE ?' if search_lemma == 'checked' else 'text_lower LIKE ?'
            #table = 'text_lemma' if search_lemma == 'checked' else 'text'
            cursor = conn.cursor()
            cursor.execute("SELECT id, text, file_load, fio, email, telefon, comment_ok, \
            comment_ruk, tests, deleted FROM files WHERE " + text_like, ["%" + search_lower + "%"])
            result = list(cursor.fetchall())
            cursor.close()
            final_result = [list(i) for i in result]
            for idx, row in enumerate(final_result):
                search = search.strip()
                final_result[idx][1] = re.sub('(' + search + ')', r"<font color='red'>\1</font>",
                                                    final_result[idx][1], flags=re.IGNORECASE)
        else:
            words = search_lower.split(' ')

            count_words = len(words)
            count_words = count_words + 1 if count_words > 1 else count_words

            table = 'text_lemma' if search_lemma == 'checked' else 'text_lower'
            text_like = [table + ' LIKE ?' for x in range(count_words)]
            text_like = ' or '.join(text_like)

            search_sql = '%'.join(words)
            list_like = ["%" + search_sql + "%"]
            if count_words > 1:
                for word in words:
                    list_like.append("%" + word + "%")

            cursor = conn.cursor()
            cursor.execute("SELECT id, text, file_load, fio, email, telefon, comment_ok, \
            comment_ruk, tests, deleted FROM files WHERE " + text_like, list_like)
            result = list(cursor.fetchall())
            cursor.close()

            final_result = [list(i) for i in result]
            if search_lemma != 'checked':
                for idx, row in enumerate(final_result):
                    search = search.strip()
                    for word in search.split(' '):
                        final_result[idx][1] = re.sub('(' + word + ')', r"<font color='red'>\1</font>",
                                                    final_result[idx][1], flags=re.IGNORECASE)
                    #str_result = str(final_result[idx][1])
                    #i = str_result.find("<font color='red'>")
                    #limit = 200
                    #if i != -1:
                    #    if i - limit > 0:
                    #        str_result = str_result[i-limit:]

                    #i = str_result.rfind("</font>")
                    #if i != -1:
                    #    if i + limit < len(str_result):
                    #        str_result = str_result[:i + limit]

                    #final_result[idx][1] = "..." + str_result + "..."

    return template('index', title = 'Поиск', page = 'search', messege = final_result, search_text = search,
                   search_lemma = search_lemma, search_strong = search_strong)

@route('/form_add', method='GET')
def form_add():
    return template('index', title = title_page_add, page = 'form_add', messege = [])

@route('/form_add', method='POST')
def do_upload():
    upload = request.files.getall('files')
    if len(upload) > 0:
        mess = []
        for file in upload:
            ext_file = file.raw_filename.split('.')[-1]
            ext_file = ext_file.lower()
            if ext_file not in ext_docs:
                mess.append(file.raw_filename + ' - формат ' + ext_file +' не поддерживается')
            else:
                mess.append(file.raw_filename + ' - загружен')

                cursor = conn.cursor()
                cursor.execute('INSERT INTO files (text, text_lower, file_load) VALUES ("-", "-", "-")')
                new_id = cursor.lastrowid
                conn.commit()
                cursor.close()

                new_file = str(new_id) + '_' + file.raw_filename
                with open(os.path.join(save_path, new_file), "wb") as file_open:
                    file_open.write(file.file.read())
                text = ' '
                if ext_file == 'docx':
                    text = docx2txt.process(os.path.join(save_path, new_file))
                if ext_file == 'pdf':
                    doc = fitz.open(os.path.join(save_path, new_file))
                    page_count = doc.pageCount
                    for num_page in range(0, page_count):
                        page = doc.loadPage(num_page)
                        text += page.getText(option="text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
                    doc.close()

                text = re.sub(r"(\s){2,}", " ", text)
                text = re.sub(r"  ", " ", text)
                text_lower = text.lower()

                doc = Doc(text)
                doc.segment(segmenter)
                doc.tag_morph(morph_tagger)
                doc.parse_syntax(syntax_parser)
                doc.tag_ner(ner_tagger)
                for token in doc.tokens:
                    token.lemmatize(morph_vocab)
                text_lemma = ' '.join([_.lemma for _ in doc.tokens])
                for span in doc.spans:
                    span.normalize(morph_vocab)
                text_normal = '<br>'.join([_.normal for _ in doc.spans])
                fio = doc.spans[0].normal
                email = re.findall(r'[a-z0-9_\.-]+@[\da-z\.-]+\.[a-z]{2,6}', text)
                email = email[0] if len(email)>0 else '-'
                telefon = re.findall(r'\+?[0-9]{9,12}', text)
                telefon = telefon[0] if len(telefon)>0 else '-'

                cursor = conn.cursor()
                cursor.execute("UPDATE files SET text = ?, text_lower = ?, file_load = ?, \
                                fio = ?, email = ?, telefon = ?, text_lemma = ?, text_normal = ? \
                                WHERE id = ?",
                               (text, text_lower, new_file, fio, email, telefon, text_lemma, text_normal,
                                new_id))
                conn.commit()
                cursor.close()

        return template('index', title = title_page_add, page = 'form_add', messege = mess)
    else:
        return template('index', title = title_page_add, page = 'form_add',
                        messege = ['Ошибка, файл не выбран!'])

@route('/key_words', method='GET')
def spec_skils_get(tab = 'new_spec'):
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM spec order by name")
    spec = list(cursor.fetchall())
    cursor.execute("SELECT id, name FROM skils order by name")
    skils = list(cursor.fetchall())
    cursor.close()
    return template('index', title = title_key_words, page = 'key_words', spec = spec, skils = skils,
                    tab = tab, messege = [], sk_name = '')

@route('/key_words', method='POST')
def spec_skils_post():
    tab = 'new_spec'
    add_spec_new = request.forms.get('add_spec_new', '').strip()
    if add_spec_new:
        tab = 'new_spec'
        spec_new = str(request.forms.decode()['spec_new'])
        cursor = conn.cursor()
        cursor.execute('INSERT INTO spec (name) VALUES (?)', [spec_new])
        new_id = cursor.lastrowid
        conn.commit()
        cursor.close()

    add_skil_new = request.forms.get('add_skil_new', '').strip()
    if add_skil_new:
        tab = 'new_spec'
        skil_new = str(request.forms.decode()['skil_new'])
        cursor = conn.cursor()
        cursor.execute('INSERT INTO skils (name) VALUES (?)', [skil_new])
        new_id = cursor.lastrowid
        conn.commit()
        cursor.close()

    add_vacancy_new = request.forms.get('add_vacancy_new', '').strip()
    if add_vacancy_new:
        tab = 'compare'
    spec_id = request.forms.get('spec_id', '').strip()
    skil_id = request.forms.get('skil_id', '').strip()
    if add_vacancy_new and spec_id and skil_id:
        spec_id = str(request.forms.decode()['spec_id'])
        skil_id = request.forms.decode().getall('skil_id')
        if len(skil_id) > 0:
            for skil in skil_id:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO spec_skil (spec_id, skil_id) VALUES (?, ?)', [spec_id, skil])
                new_id = cursor.lastrowid
                conn.commit()
                cursor.close()

    public_vacancy = request.forms.get('public_vacancy', '').strip()
    if public_vacancy:
        tab = 'opinion'

    return spec_skils_get(tab)

@route('/download/<filename:path>')
def download(filename):
    return static_file(filename, root=save_path, download=filename)

@route('/static/<filename:path>')
def server_static(filename):
    return static_file(filename, root='static')

@route('/is_ajax_1', method='POST')
def is_ajax_1():
    spec_id = request.forms.get('spec_id')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and spec_id:
        spec_id = int(spec_id)
        cursor = conn.cursor()
        cursor.execute("SELECT skils.id skils_id, spec_skil.id spec_skil_id, skils.name from skils \
                        left join spec_skil on skils.id = spec_skil.skil_id and spec_skil.spec_id = ? \
                        order by skils.name", [spec_id])
        skils = list(cursor.fetchall())
        cursor.close()
        option = ''
        if len(skils) > 0:
            for skil in skils:
                disabled = 'disabled' if skil[1] else ''
                option += '<option value="' + str(skil[0]) +'" ' + disabled +'>' + str(skil[2]) +'</option>'
        return option
    else:
        return False

@route('/is_ajax_2', method='POST')
def is_ajax_2():
    public_id = request.forms.get('public_id')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and public_id:
        public_id = int(public_id)
        cursor = conn.cursor()
        cursor.execute("SELECT sk.name FROM spec_skil as ss, spec as sp, skils as sk \
                        where ss.spec_id = sp.id and ss.skil_id = sk.id and ss.spec_id = ? \
                        order by sk.name", [public_id])
        skils = list(cursor.fetchall())
        cursor.close()
        skils =  ', '.join([_[0] for _ in skils])
        return skils
    else:
        return False

def selection():
    cursor = conn.cursor()
    cursor.execute("SELECT s.id, s.name, count(s.id) count_skil FROM spec_skil as ss, spec as s \
                    where ss.spec_id = s.id GROUP by s.id, s.name order by s.name")
    skils = list(cursor.fetchall())
    cursor.close()
    return skils

@route('/selection', method='GET')
def selection_get():
    skils = selection()
    return template('index', title = 'Подбор вакансий', page = 'selection', spec = skils,
                    sk_name = '', sp_name = '', messege = '')

@route('/selection', method='POST')
def selection_post():
    select_skils = selection()
    spec_id = request.forms.get('spec_id')
    final_result = []
    sk_name = ''
    sp_name = ''
    if spec_id:
        spec_id = int(spec_id)
        cursor = conn.cursor()
        cursor.execute("SELECT sp.name, sk.name FROM spec_skil as ss, spec as sp, skils as sk \
                        where ss.spec_id = sp.id and ss.skil_id = sk.id and ss.spec_id = ? \
                        order by sk.name", [spec_id])
        result = list(cursor.fetchall())
        cursor.close()
        if len(result) > 0:
            sk_name =  ', '.join([_[1] for _ in result])
            sp_name = result[0][0]

            #sk_name_words = sk_name.split(', ')
            #for words in sk_name_words:
            #doc = Doc(re.sub(r"\W", " ", sk_name))
            doc = Doc(sk_name)
            doc.segment(segmenter)
            doc.tag_morph(morph_tagger)
            doc.parse_syntax(syntax_parser)
            doc.tag_ner(ner_tagger)
            for token in doc.tokens:
                token.lemmatize(morph_vocab)
            sk_name_lemme = ' '.join([_.lemma for _ in doc.tokens])
            sk_name += '<br>[' +sk_name_lemme+ ']'

            words = sk_name_lemme.split(', ')

            count_words = len(words)
            #count_words = count_words + 1 if count_words > 1 else count_words

            text_like = ['text_lemma LIKE ?' for x in range(count_words)]
            text_like = ' or '.join(text_like)

            #search_sql = '%'.join(words)
            #list_like = ["%" + search_sql + "%"]
            list_like = []
            #if count_words > 1:
            for word in words:
                list_like.append("% " + word.strip() + " %")

            cursor = conn.cursor()
            cursor.execute("SELECT id, text_lemma, file_load, fio, email, telefon, comment_ok, \
            comment_ruk, tests, deleted FROM files WHERE " + text_like, list_like)
            result = list(cursor.fetchall())
            cursor.close()
            final_result = [list(i) for i in result]

            for idx, row in enumerate(final_result):
                #search = search.strip()
                for word in words:
                    final_result[idx][1] = re.sub('(' + word + ')', r"<font color='red'>\1</font>",
                                                final_result[idx][1], flags=re.IGNORECASE)
                final_result[idx][9] = len(re.findall(r'font color', final_result[idx][1]))

            final_result = sorted(final_result, key=lambda x: -x[9])

    return template('index', title = 'Подбор вакансий', page = 'selection', spec = select_skils,
                    sk_name = sk_name, sp_name = sp_name, messege = final_result)


application = default_app()
#run(host='localhost', port=8080)
