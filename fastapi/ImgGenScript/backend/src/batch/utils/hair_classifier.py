class HairClassifier:
    @staticmethod
    def classify_type(hair_type: str) -> str:
        normalized = hair_type.lower()
        if 'straight' in normalized:
            return 'straight'
        elif 'wavy' in normalized:
            return 'wavy'
        elif 'curly' in normalized:
            return 'curly'
        elif 'coily' in normalized or 'afro' in normalized:
            return 'coily'
        return 'straight'

    @staticmethod
    def classify_length(hair_length: str) -> str:
        normalized = hair_length.lower()
        if 'long' in normalized:
            return 'long'
        elif 'shoulder' in normalized:
            return 'medium'
        elif 'short' in normalized:
            return 'short'
        return 'long'