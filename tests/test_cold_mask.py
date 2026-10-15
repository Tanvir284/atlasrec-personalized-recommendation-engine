import torch
from atlasrec_ml.models import Towers


def test_withheld_item_has_no_collaborative_id_component():
    torch.manual_seed(42)
    towers=Towers(3,4,2)
    content=torch.randn(3,4)
    towers.id_mask[1]=0
    before=towers.item_vectors(content)[1].detach().clone()
    with torch.no_grad():
        towers.items.weight[1].fill_(100000)
    after=towers.item_vectors(content)[1].detach()
    expected=torch.nn.functional.normalize(towers.item_content(content)[1],dim=0).detach()
    assert torch.allclose(before,after)
    assert torch.allclose(after,expected)
