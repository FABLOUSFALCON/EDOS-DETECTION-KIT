class FlagCount:
    """This class extracts features related to the Flags Count.

    TCP Flags: (UDP does not have flag)
        SYN: Synchronization
        ACK: Acknowledgement
        FIN: Finish
        RST: Reset
        URG: Urgent
        PSH: Push
        CWR
        ECE
    """

    def __init__(self, flow):
        self.flow = flow

    def count(self, flag, packet_direction=None) -> bool:
        """Count packets by direction.

        Returns:
            packets_count (int):

        """
        count = 0
        if packet_direction is not None:
            packets = (
                packet
                for packet, direction in self.flow.packets
                if direction == packet_direction
            )
        else:
            packets = (packet for packet, _ in self.flow.packets)

        for packet in packets:
            if "TCP" in packet and hasattr(packet["TCP"], "flags"):
                tcp_flags = packet["TCP"].flags
                if isinstance(tcp_flags, str):
                    # String-based flag checking (legacy)
                    if flag[0] in tcp_flags:
                        count += 1
                else:
                    # Bit-based flag checking (proper TCP flags)
                    flag_values = {
                        "F": 0x01,  # FIN
                        "S": 0x02,  # SYN
                        "R": 0x04,  # RST
                        "P": 0x08,  # PSH
                        "A": 0x10,  # ACK
                        "U": 0x20,  # URG
                        "E": 0x40,  # ECE
                        "C": 0x80,  # CWR
                    }
                    if flag[0] in flag_values and (tcp_flags & flag_values[flag[0]]):
                        count += 1
        return count
