"""One-time CSO ontology + word2vec download (~2GB). Run once per env."""
from cso_classifier.classifier import CSOClassifier
cc = CSOClassifier()
cc.setup()
print("CSO setup complete.")
