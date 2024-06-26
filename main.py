import re
import pandas as pd
import numpy as np

from collections import defaultdict
from bitstring import BitArray

from utils import encode_delta_single, encode_gamma_single, decode_delta_single, decode_gamma_single


class InvertedIndex:
    def __init__(self):
        self.columns_to_keep = set(['date', 'message', 'views', 'forwards', 'replies'])
        self.list_df = []
        self.df = None
        self.inv_idx = defaultdict(list)
        self.inv_idx_delta = defaultdict(list)
        self.inv_idx_gamma = defaultdict(list)


    def merge_jsons(self, paths):
        if len(paths) > 0:
            for path in paths:
                df = pd.read_json(path)
                df = df.drop(columns=list(set(df.columns) - self.columns_to_keep))
                self.list_df.append(df)

            self.df = pd.concat(self.list_df, ignore_index=True)
            self.df = self.df[self.df['message'].notna()] # filter out Nans and empty messages
            self.df = self.df[self.df['message'] != '']
        else:
            raise ValueError('Empty paths!')


    def preprocess(self, message):
        """ Remove punctuation, cast to lower case and split the message """
        cleaned_message = re.sub(r'\W+', ' ', message.lower())
        return set(cleaned_message.split())


    def get_inverted_index(self):
        for idx, row in self.df.iterrows():
            if idx > 0:
                words = self.preprocess(row['message'])
                for word in words:
                    self.inv_idx[word].append(idx)

        for k, v in self.inv_idx.items():
            self.inv_idx[k] = sorted(list(set(v)))


    def reset_inv_idx(self):
        if len(self.inv_idx.keys()) > 0:
            self.inv_idx = defaultdict(list)
        if len(self.inv_idx_delta.keys()) > 0:
            self.inv_idx_delta = defaultdict(list)
        if len(self.inv_idx_gamma.keys()) > 0:
            self.inv_idx_gamma = defaultdict(list)


    def encode_delta(self):
        for word, list_idx in self.inv_idx.items():
            diff = list(np.diff(list_idx))
            diff.insert(0, list_idx[0])
            encoded = [encode_delta_single(number) for number in diff]
            self.inv_idx_delta[word] = encoded


    def encode_gamma(self):
        for word, list_idx in self.inv_idx.items():
            diff = list(np.diff(list_idx))
            diff.insert(0, list_idx[0])
            encoded = [encode_gamma_single(number) for number in diff]
            self.inv_idx_gamma[word] = encoded


    def find(self, text, encoding=None):
        words = self.preprocess(text)
        possible_documents = []

        if encoding is None:
            for word in words:
                if word in self.inv_idx:
                    possible_documents.append(set(self.inv_idx[word]))
        elif encoding == 'delta':
            for word in words:
                if word in self.inv_idx_delta:
                    cumsum_idx = np.cumsum([decode_delta_single(enc) for enc in self.inv_idx_delta[word]])
                    possible_documents.append(set(list(cumsum_idx)))
        elif encoding == 'gamma':
            for word in words:
                if word in self.inv_idx_gamma:
                    cumsum_idx = np.cumsum([decode_gamma_single(enc) for enc in self.inv_idx_gamma[word]])
                    possible_documents.append(set(list(cumsum_idx)))

        if len(possible_documents) == 0:
            return 'There are no related documents'

        intersection = set.intersection(*possible_documents)

        # delete words from the end until we get any intersection
        while not intersection:
            possible_documents = possible_documents[:-1]
            intersection = set.intersection(*possible_documents)

        return self.df.loc[list(intersection)]
