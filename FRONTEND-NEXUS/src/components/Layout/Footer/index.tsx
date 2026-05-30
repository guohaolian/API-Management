import React from "react";
import styles from "./index.module.less";

const Footer: React.FC = () => {
    return (
        <div className={styles.footer}>
            <span>
                Copyright © {new Date().getFullYear()}{" "}
                <a
                    href="mailto:1040071899@qq.com"
                    style={{ color: "#007bff", textDecoration: "none" }}
                >
                    Guo HL
                </a>
                . All Rights Reserved.
            </span>
        </div>
    );
};

export default Footer;
