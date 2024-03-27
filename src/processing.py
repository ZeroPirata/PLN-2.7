import re
import httpx
import spacy
import json
import unicodedata


from spellchecker import SpellChecker
from bs4 import BeautifulSoup
from functools import wraps
from time import perf_counter


def timing(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = perf_counter()
        result = func(*args, **kwargs)
        end_time = perf_counter()
        elapsed_time_ms = round(((end_time - start_time) * 1000), 2)
        print(f"Função executada com: {elapsed_time_ms}")
        return result, elapsed_time_ms

    return wrapper


class Processing:
    def __init__(self, url, section, tag) -> None:
        self._url = url
        self._section = section
        self._tag = tag
        self._expansion_dict_file = "src/words.json"
        self.__init_processing()

    def __init_processing(self):
        """Inicialização das função de processamento dos dados"""
        self._raspagem = self.__raspagem()
        self._remocao_ruido = self.__remocao_ruido()
        self._tokenizacao_frases = self.__tokenizacao_por_frases()
        self._tokenizacao_palavras = self.__tokenizacao_por_palavras()
        self._expansao_palavras = self.__expansao_palavras()
        self._correcao_palavras = self.__correcao_palavras()

    @timing
    def __raspagem(self):
        """Fazer a leitura da url e pegar seu HTML."""
        r = httpx.get(self._url)
        if r.status_code != 200:
            return ""
        return r.text

    @timing
    def __remocao_ruido(self):
        """Remoção da parte do HTML e deixando apenas a sessão que contem o comentario dos usuarios dentro da página"""
        soup = BeautifulSoup(self._raspagem[0], "html.parser")
        [s.extract() for s in soup(["iframe", "script"])]
        session = soup.find(self._tag, self._section)
        stripped_text = session.get_text()
        stripped_text = re.sub(r"\s+", " ", stripped_text)
        stripped_text = stripped_text.replace("\n", " ")
        return stripped_text.strip()

    @timing
    def __tokenizacao_por_frases(self):
        """Separação das frases que vem da remoção de ruido, onde ele vai devolver todas as frases separadas pelas pontuação"""
        model_spacy = spacy.load("pt_core_news_sm")
        word_tokens = model_spacy(self._remocao_ruido[0])
        sentences = [
            self.remove_special_characters(str(sent)) for sent in word_tokens.sents
        ]
        sentence_tokens = sentences
        return sentence_tokens

    @timing
    def __tokenizacao_por_palavras(self):
        """Criação de Vetor de vetores com as palavras de cada frase"""
        sentences = [lst for lst in self._tokenizacao_frases[0] if lst]
        words_tokens = [frase.split() for frase in sentences]
        return words_tokens

    @timing
    def __expansao_palavras(self):
        """Função para expandir palavras e corrigir acentuação"""
        expansion_dict: dict = self.load_expansion_dict(self._expansion_dict_file)
        all_words = self._tokenizacao_palavras[0]
        expanded_tokenizacao_palavras = []

        for words in all_words:
            expanded_words = []
            for i, word in enumerate(words):
                expanded_word = self.expand_word(word.lower(), expansion_dict)
                words[i] = expanded_word
                expanded_words.append(expanded_word)
            expanded_tokenizacao_palavras.append(expanded_words)

        return expanded_tokenizacao_palavras

    @timing
    def __correcao_palavras(self):
        portuguese = SpellChecker(language="pt")
        all_words = self._expansao_palavras[0]
        correcao_palavra_list = []
        for words in all_words:
            correcao_lista = []
            for word in words:
                correction_word = portuguese.correction(word)
                correcao_lista.append(
                    correction_word if correction_word is not None else word
                )
            correcao_palavra_list.append(correcao_lista)

        return correcao_palavra_list

    @staticmethod
    def load_expansion_dict(expansion_dict_file):
        """Carrega o dicionário de expansão de palavras do arquivo"""
        with open(expansion_dict_file, "r", encoding="utf-8") as f:
            expansion_dict = json.load(f)
        return expansion_dict

    @staticmethod
    def expand_word(word, expansion_dict):
        get_value = expansion_dict.get(word)
        if expansion_dict.get(word) is not None:
            return get_value
        else:
            return word

    @staticmethod
    def remove_special_characters(text):
        text = (
            unicodedata.normalize("NFKD", text)
            .encode("ascii", "ignore")
            .decode("utf-8", "ignore")
        )
        special_chars_regex = r"[^a-zA-Z\s]"
        text_cleaned = re.sub(special_chars_regex, "", text)

        return text_cleaned

    def __create_dict(self, entrada, saida, etapa):
        return {
            "entrada": entrada,
            "saida": saida[0],
            "tempo": saida[1],
            "etapa": etapa,
        }

    def processing(self):
        steps = [
            ("Raspagem", self._url, self._raspagem),
            ("Remoção de ruído", self._raspagem[0], self._remocao_ruido),
            (
                "Tokenização por frases",
                self._remocao_ruido[0],
                self._tokenizacao_frases,
            ),
            (
                "Tokenização por palavras",
                self._tokenizacao_frases[0],
                self._tokenizacao_palavras,
            ),
            (
                "Expansão de siglas e abreviaturas",
                self._tokenizacao_palavras[0],
                self._expansao_palavras,
            ),
            (
                "Correção de caracteres incorretos",
                self._expansao_palavras[0],
                self._correcao_palavras,
            ),
        ]

        return [
            self.__create_dict(entrada, saida_func, etapa)
            for etapa, entrada, saida_func in steps
        ]
