from capability_commons.domain.enums import COType
from capability_commons.schemas.structured_data import validate_structured_data


def test_skill_guide_structured_data_validation() -> None:
    data = validate_structured_data(
        COType.SKILL_GUIDE,
        {
            'performance_statement': 'Estimate runtime for one backup scenario.',
            'learning_objectives': ['Identify wattage'],
            'tools': ['calculator'],
            'materials': ['labels'],
            'steps_summary': ['List loads'],
            'success_criteria': ['Table complete'],
            'failure_modes': ['Ignoring usable capacity'],
            'safety_boundary': 'Do not modify house wiring.',
            'stop_conditions': ['Unknown wiring conditions'],
            'teach_forward': {
                'three_minute_script': 'Explain watts and watt-hours.',
                'ten_minute_outline': ['Intro', 'Formula'],
                'handout_points': ['Watts', 'Watt-hours'],
            },
        },
    )
    assert data['teach_forward']['handout_points'] == ['Watts', 'Watt-hours']
