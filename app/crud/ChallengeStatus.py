from enum import Enum

class ChallengeStatus(str, Enum):
    TOUS = "tous"
    A_VENIR = "a_venir"
    EN_COURS = "en_cours"
    TERMINE = "termine"