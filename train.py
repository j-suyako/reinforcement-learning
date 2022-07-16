from data.generator import Dataset
from nets.model import DinoModel
from tensorflow.keras import optimizers, losses, backend as K
import tensorflow as tf

from util.agent import Agent


class Trainer(object):
    def __init__(self, dataset: Dataset) -> None:
        self.policy_model = DinoModel()
        self.target_model = DinoModel()
        self.dataset = dataset
        self.dataset.update_model(self.policy_model)
        self.batch_size = 32
        self.gamma = 0.95
        self.epochs = 100
        self.target_update = 10
        self.optimizer = optimizers.Adam(1e-4, epsilon=1e-8)
        self.summary_write = tf.summary.create_file_writer(r'./logs')

    def train(self):
        temp = tf.random.normal((4, 80, 80, 4))
        self.policy_model(temp, training=False)
        self.target_model(temp, training=False)  # build model
        steps = 0
        self.dataset.update_epsilon(steps)
        for epoch in range(self.epochs):
            # K.set_value(self.optimizer.learning_rate, 1e-4 * 2.7 ** (-epoch // 200))
            if epoch % self.target_update == 0:
                self.target_model.set_weights(self.policy_model.get_weights())
            loss = 0
            epoch_step = 0
            for x in self.dataset.generator(self.batch_size, 4):
                if x is None:
                    continue
                epoch_step += 1
                steps += 1
                loss += self.train_step(x)
                self.dataset.update_epsilon(steps)
            if epoch_step > 0:
                with self.summary_write.as_default():
                    tf.summary.scalar('step', epoch_step, step=epoch)
                    tf.summary.scalar('loss', loss / epoch_step, step=epoch)
                print(f"epoch: {epoch}, step:{epoch_step}, loss: {loss / epoch_step}")

    def train_step(self, x):
        with tf.GradientTape() as tape:
            s, a, r, sn = x
            act = list(zip(range(a.shape[0]), a))
            Q = tf.gather_nd(self.policy_model(s, training=True), act)
            an = tf.argmax(self.policy_model(sn, training=False), axis=-1).numpy()
            actn = list(zip(range(an.shape[0]), an))
            Qn = tf.gather_nd(self.target_model(sn, training=False), actn)
            Qn = tf.stop_gradient(Qn)
            Qn = tf.where(r == -100, r, r + self.gamma * Qn)
            # loss = tf.reduce_mean((Q - Qn) ** 2)
            loss = tf.losses.huber(Q, Qn)
        grads = tape.gradient(loss, self.policy_model.trainable_variables)
        grads = [tf.clip_by_value(grad, -1., 1.) for grad in grads]
        self.optimizer.apply_gradients(zip(grads, self.policy_model.trainable_variables))
        return loss


if __name__ == "__main__":
    dataset = Dataset()
    trainer = Trainer(dataset)
    trainer.train()