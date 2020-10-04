from datetime import datetime
from time import sleep
from itertools import count

from bs4 import BeautifulSoup as bs
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from tqdm import tqdm


def get_html(url):
    options = Options()
    options.headless = True
    driver = Chrome(options=options)
    driver.get(url)
    sleep(3)
    html = driver.page_source
    driver.quit()
    return bs(html, 'html.parser')


def get_links_of_reclamation(bs_html: bs):
    boxes = bs_html.find_all(
        'a',
        {'ui-sref': 'businessComplain({ company: (result.company.shortname|companyShortname), '
                    'productName: (complain.title|fullUrlDecorator), productId: complain.id})'}
    )
    href_links = [box.get('href') for box in boxes]
    if not boxes:
        boxes = bs_html.find('div', {'class': 'sc-iELTvK hisDVE'}).find_all('a', href=True)
        href_links = [box['href'] for box in boxes]
    return [f'https://www.reclameaqui.com.br/{link}' for link in href_links]


def get_all_links(url, limit=None):
    if isinstance(limit, int):
        limit /= 10
    all_links = set()
    counter = count(start=1)
    while True:
        try:
            last = len(all_links)
            bs_html = get_html(f'{url}?pagina={next(counter)}')
            href_links = set(get_links_of_reclamation(bs_html))
            if href_links:
                print(f'Foram achadas {len(href_links)} links novos')
                all_links = all_links.union(href_links)
                if len(all_links) == last or limit == last:
                    break
                else:
                    print(f'ainda falta algumas paginas:  proxima pagina será -> {counter}')
            else:
                print('não conseguimos encontrar nenhum link')
                print(f'ainda falta algumas paginas:  proxima pagina será -> {counter}')
        except:
            pass
    return all_links


def get_date(bs_html: bs):
    date_formatted = None
    date = bs_html.find('div', {'class': 'col-md-10 col-sm-12'}).find_all('li', {'class': 'ng-binding'})[-1].text
    for str_to_datetime in date.split(' '):
        try:
            date_formatted = datetime.strptime(str_to_datetime, '%m/%d/%y')
        except ValueError:
            if not date_formatted:
                date_formatted = None
    return date_formatted


def data_basic(bs_html: bs):
    date = get_date(bs_html)
    dict_basic = {
        'id': bs_html.find('div', {'class': 'col-md-10 col-sm-12'}).find('b').text.split(' ')[-1],
        'date': date,
        'title': bs_html.find('div', {'class': 'col-md-10 col-sm-12'}).find('h1').text,
        'status': bs_html.find(
            'span', {'ng-bind-html': '::reading.validateIcon(reading.complains).text'}
        ).find('strong').text,
        'reclamation': bs_html.find('div', {'class': 'complain-body'}).find('p').text
    }
    return dict_basic


def get_dialogue(bs_html: bs):
    titles = bs_html.find_all('p', {'class': "title ng-scope"})
    text_titles = [unit.text for unit in titles if unit.text != 'Consideração final do Consumidor']

    conversations = bs_html.find_all('p', {'ng-if': "interaction.type != 'FINAL_ANSWER'"})
    text_conversations = [unit.text for unit in conversations]
    list_dialogue = []
    if len(text_conversations) == len(text_titles):
        for i in range(len(text_conversations)):
            list_dialogue.append(
                {
                    text_titles[i]: text_conversations[i]
                }
            )
    return list_dialogue


def final_consideration(bs_html: bs):
    return {'final_consideration': bs_html.find_all('p', {'ng-if': "interaction.type == 'FINAL_ANSWER'"})[-1].text}


def get_evaluation(bs_html: bs):
    evaluation = [unit.text for unit in bs_html.find('div', {'class': 'user-upshot-seals ng-scope'}).find_all('p')]
    grade = None
    would_do_business_again = None
    if evaluation:
        for check in evaluation:
            try:
                grade = float(check)
            except ValueError:
                if len(check) == 3:
                    would_do_business_again = check
    dict_evaluation = {
        'grade': grade,
        'would_do_business_again': would_do_business_again
    }
    return dict_evaluation


def get_all_reclamation(html):
    bs_html = get_html(html)
    evaluation = get_evaluation(bs_html)
    basic = data_basic(bs_html)
    dialogue = {'dialogue': get_dialogue(bs_html)}
    try:
        finish = final_consideration(bs_html)
    except IndexError:
        finish = {'final_consideration': None}
    complete = {**basic, **dialogue, **finish, **evaluation}
    return complete


def crawling(link, limit=None):
    all_html = get_all_links(f'{link}lista-reclamacoes/', limit)
    data = list()
    error = list()
    for html in tqdm(all_html):
        try:
            data.append(get_all_reclamation(html))
        except Exception as e:
            print(e)
            error.append({'error': e, 'html': html})
    return data


if __name__ == "__main__":
    import pandas as pd
    url = 'https://www.reclameaqui.com.br/empresa/webmotors-compreauto-vmotors/'
    data = crawling(url)
    df = pd.DataFrame(data)
    df.to_csv(f'{url[39:-1]}.csv')
