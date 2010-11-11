#!/usr/bin/python
#
# Author: Peter Prettenhofer <peter.prettenhofer@gmail.com>
#
# License: BSD Style

import sys
import re
import optparse

from ..io import conll
from ..tagger import tagger

__version__ = "0.1"

WORD, POS, NP, LEMMA = 0, 1, 2, 3


def numify(s):
    """Abstract representation of digits.
    """
    if sum((1 for c in s if not c.isdigit())) > 2:
        return s
    else:
        return "".join(["*d*" if c.isdigit() else c for c in s])


## Extract features from the current context.
# all local variables are used as binary features:
# varname(varvalue) = 1
def fd(sent, index, length):
    """Feature detector for CoNLL 2003.
    """
    context = lambda idx, field: sent[index + idx][field] \
              if index+idx >= 0 and index + idx < length \
              else "<s>" if index+idx < 0 \
              else "</s>"

    ## tokens in a 5 token window x_{i-2}..x_{i+2}
    w = context(0, WORD)
    pre_w = context(-1, WORD)
    pre_pre_w = context(-2, WORD)
    post_w = context(1, WORD)
    post_post_w = context(2, WORD)

    bigram = "/".join([pre_w, w])
    pre_bigram = "/".join([pre_pre_w, pre_w])
    post_bigram = "/".join([w, post_w])
    post_post_bigram = "/".join([post_w, post_post_w])

    ## pos in a 5 token window
    pos = context(0, POS)
    pre_pos = context(-1, POS)
    post_pos = context(1, POS)
    pre_pre_pos = context(-2, POS)
    post_post_pos = context(2, POS)
    post_post_pos = context(2, POS)

    ## Word shape features
    istitle = w.istitle()
    isdigit = w.isdigit()
    isupper = w.isupper()
    isalnum = w.isalnum()
    hyphen  = "-" in w
    num_w = numify(w)

    pre_istitle = pre_w.istitle()
    pre_isdigit = pre_w.isdigit()
    pre_isupper = pre_w.isupper()
    pre_hyphen  = "-" in pre_w
    pre_isalnum = pre_w.isalnum()
    num_pre_w = numify(pre_w)

    pre_pre_istitle = pre_pre_w.istitle()
    pre_pre_isdigit = pre_pre_w.isdigit()
    pre_pre_isupper = pre_pre_w.isupper()
    pre_pre_hyphen  = "-" in pre_pre_w
    pre_pre_isalnum = pre_pre_w.isalnum()
    num_pre_pre_w = numify(pre_pre_w)

    post_istitle = post_w.istitle()
    post_isdigit = post_w.isdigit()
    post_isupper = post_w.isupper()
    post_hypen   = "-" in post_w
    post_isalnum = post_w.isalnum()
    num_post_w = numify(post_w)

    post_post_istitle = post_post_w.istitle()
    post_post_isdigit = post_post_w.isdigit()
    post_post_isupper = post_post_w.isupper()
    post_post_hypen   = "-" in post_post_w
    post_post_isalnum = post_post_w.isalnum()
    num_post_post_w = numify(post_post_w)
    
    ## 2-4 suffixes in a 1 token window
    w_suffix1 = w[-1:]
    w_suffix2 = w[-2:]
    w_suffix3 = w[-3:]
    w_suffix4 = w[-4:]

    pre_w_suffix1 = pre_w[-1:]
    pre_w_suffix2 = pre_w[-2:]
    pre_w_suffix3 = pre_w[-3:]
    pre_w_suffix4 = pre_w[-4:]

    post_w_suffix1 = post_w[-1:]
    post_w_suffix2 = post_w[-2:]
    post_w_suffix3 = post_w[-3:]
    post_w_suffix4 = post_w[-4:]

    ## 2-4 prefixes in a 1 token window
    w_prefix3 = w[:3]
    w_prefix4 = w[:4]
 
    pre_w_prefix3 = pre_w[:3]
    pre_w_prefix4 = pre_w[:4]

    post_w_prefix3 = post_w[:3]
    post_w_prefix4 = post_w[:4]

    ## Noun phrase
    np = context(0,NP)
    np_w = "/".join([np,w])
    pre_np = context(-1, NP)
    post_np = context(1, NP)

    ## Extract features from local scope
    features = locals()
    del features["context"]
    del features["sent"]
    del features["index"]
    del features["length"]
    features = features.items()
    return features


def hd(tags, sent, index, length):
    context = lambda idx, field: sent[index + idx][field] \
              if index+idx >= 0 and index + idx < length \
              else "<s>" if index+idx < 0 \
              else "</s>"

    pre_tag = tags[index - 1] if index - 1 >= 0 else "<s>"
    pre_tag_w = "/".join([pre_tag, context(0, WORD)])
    tag_bigram = "/".join([tags[index - 2] if index - 2 >= 0 else "<s>",
                           pre_tag])
    history = locals()
    del history["context"]
    del history["tags"]
    del history["sent"]
    del history["index"]
    del history["length"]
    return history.items()

class ASO(object):
    def __init__(self, model, reader):
        self.reader = reader
        self.fidx_map = model.fidx_map
        self.ds = tagger.build_examples(reader, model.fd, model.hd,
                                        model.V, model.T)

    def instances_by_pos_prefix(prefix):
        indices = []
        i = 0
        for sent in reader:
            for token in sent:
                if token[POS].startswith(prefix):
                    indices.append(i)
                    i += 1
        return np.array(indices)

    def filter_noun_adjectives(self):
        ds = self.ds
        nn_indices = self.instances_by_pos_prefix("NN")
        jj_indices = self.instances_by_pos_prefix("JJ")
        indices = np.union(nn_indices, jj_indices)
        ds.instances = ds.instances[indices]
        ds.labels = ds.labels[indices]
        ds.n = ds.labels.shape[0]
        self.ds = ds


def train_args_parser():
    """Create argument and option parser for the
    training script. 
    """
    description = """    """
    parser = optparse.OptionParser(usage="%prog [options] " \
                                   "train_file model_file",
                                   version="%prog " + __version__,
                                   description = description)
    parser.add_option("-v", "--verbose",
                      dest="verbose",
                      help="verbose output",
                      default=1,
                      metavar="[0,1,2]",
                      type="int")
    parser.add_option("-r", "--reg",
                      dest="reg",
                      help="regularization parameter. ",
                      default=0.00001,
                      metavar="float",
                      type="float")
    parser.add_option("-E", "--epochs",
                      dest="epochs",
                      help="Number of training epochs. ",
                      default=100,
                      metavar="int",
                      type="int")
    parser.add_option("--min-count",
                      dest="minc",
                      help="min number of occurances.",
                      default=0,
                      metavar="int",
                      type="int")
    parser.add_option("--max-unlabeled",
                      dest="max_unlabeled",
                      help="max number of unlabeled documents to read;" \
                      "-1 for unlimited.",
                      default=-1,
                      metavar="int",
                      type="int")
    parser.add_option("-l", "--lang",
                      dest="lang",
                      help="The language (`en` or `de`).",
                      default="en",
                      metavar="str",
                      type="str")
    parser.add_option("--shuffle",
                      action="store_true",
                      dest="shuffle",
                      default=False,
                      help="Shuffle the training data after each epoche.")
    parser.add_option("--stats",
                      action="store_true",
                      dest="stats",
                      default=False,
                      help="Print model statistics.")
    parser.add_option("--aso",
                      action="store_true",
                      dest="aso",
                      default=False,
                      help="Use Alternating Structural Optimization.")
    parser.add_option("-u", "--unlabeled",
                      dest="funlabeled",
                      help="FILE containing unlabeled data.",
                      metavar="str",
                      type="str")
    return parser


def train():
    """Training script for Named Entity Recognizer.
    """
    parser = train_args_parser()
    options, argv = parser.parse_args()
    if len(argv) != 2:
        parser.error("incorrect number of arguments (use `--help` for help).")
    f_train = argv[0]
    f_model = argv[1]
    train_reader = conll.Conll03Reader(f_train, options.lang)
    #model = tagger.AvgPerceptronTagger(fd, hd)
    model = tagger.GreedySVMTagger(fd, hd, verbose=options.verbose)
    model.feature_extraction(train_reader, options.minc)
    if options.aso:
        unlabeled_reader = conll.Conll03Reader(options.funlabeled, options.lang)
        aso = ASO()
    model.train(reg=options.reg, epochs=options.epochs, shuffle=options.shuffle)
    model.save(f_model)
    if options.stats:
        print "------------------------------"
        print " Stats\n"
        model.describe(k=40)


def predict():
    """Test script for Named Entity Recognizer.
    """
    def usage():
        print """Usage: %s [OPTIONS] MODEL_FILE TEST_FILE PRED_FILE
        Load NER model from MODEL_FILE, test the model on
        TEST_FILE and write predictions to PRED_FILE.
        The predictions are appended to the test file.
        Options:
          -h, --help\tprint help.
          -l, --lang\tThe language.

        """ % sys.argv[0]
    argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        usage()
        sys.exit(-2)
    if "-l" in argv:
        i = argv.index("-l")
        argv[i] = "--lang"
    if "--lang" in argv:
        i = argv.index("--lang")
        lang = argv[i + 1]
        del argv[i:i+2]
    else:
        lang = "en"
    if len(argv) != 3:
        print "Error: wrong number of arguments. "
        usage()
        sys.exit(-2)
    
    model = tagger.GreedySVMTagger(fd, hd)
    print >> sys.stderr, "loading tagger...",
    sys.stderr.flush()
    model.load(argv[0])
    print >> sys.stderr, "[done]"
    test_reader = conll.Conll03Reader(argv[1], lang)
    if argv[2] != "-":
        f = open(argv[2], "w+")
    else:
        f = sys.stdout
    test_reader.write_sent_predictions(model, f, raw=False)
    f.close()