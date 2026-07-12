import cv2

def find(screen, template_path, threshold=0.8):
    tpl = cv2.imread(template_path)
    if tpl is None:
        return None
    for scale in [0.9, 1.0, 1.1]:
        resized = cv2.resize(tpl, None, fx=scale, fy=scale)
        if resized.shape[0] > screen.shape[0] or resized.shape[1] > screen.shape[1]:
            continue
        res = cv2.matchTemplate(screen, resized, cv2.TM_CCOEFF_NORMED)
        _, maxval, _, maxloc = cv2.minMaxLoc(res)
        if maxval >= threshold:
            h, w = resized.shape[:2]
            return (maxloc[0] + w // 2, maxloc[1] + h // 2)
    return None
