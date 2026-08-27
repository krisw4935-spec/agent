import { Modal } from '@douyinfe/semi-ui-19'
import { useImageModalStore } from '@/store/image-modal-store'

export function ImageModal() {
  const openSrc = useImageModalStore(state => state.openSrc)
  const close = useImageModalStore(state => state.close)

  return (
    <Modal
      modalContentClass=""
      visible={Boolean(openSrc)}
      onCancel={close}
      footer={null}
      width="auto"
      centered
      zIndex={2100}
      maskStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.85)' }}
      bodyStyle={{ padding: 0, background: 'transparent' }}
      header={null}
    >
      {openSrc
        ? (
            <img
              src={openSrc}
              alt="预览大图"
              className="max-w-90vw max-h-85vh block rounded-2"
            />
          )
        : null}
    </Modal>
  )
}
